// JobHunter desktop — Tauri v2 shell + Python sidecar IPC (C-031, SDD §11.1).
//
// The Python core runs as a child process.  Rust writes one JSON request to
// its stdin and reads newline-delimited JSON events from its stdout:
//   - {"type":"progress", ...}  forwarded as Tauri events to the frontend
//   - {"type":"result",  ...}  returned as the command's Ok value
//   - {"type":"error",  ...}  turned into an Err return
//
// All Python logs go to the child's stderr and are NOT read here, so they
// never corrupt the JSON stream (SDD §11.1 rule: stdout is the IPC channel).

use std::io::{BufRead, BufReader, Write};
use std::process::{Command, Stdio};

use serde::{Deserialize, Serialize};
use tauri::Emitter;

// ---------------------------------------------------------------------------
// IPC types
// ---------------------------------------------------------------------------

/// One progress event forwarded to the Vue frontend.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProgressPayload {
    pub run_id: Option<String>,
    pub stage: Option<String>,
    pub state: Option<String>,
    pub message: Option<String>,
    pub current: Option<u64>,
    pub total: Option<u64>,
    pub metric: Option<serde_json::Value>,
}

// ---------------------------------------------------------------------------
// Helper: locate the Python executable
// ---------------------------------------------------------------------------

/// Returns the Python executable path.
///
/// Resolution order:
/// 1. `JOBHUNTER_PYTHON` environment variable (useful in tests and CI).
/// 2. `.venv/Scripts/python.exe` relative to `JOBHUNTER_ROOT` (or CWD).
/// 3. `py` (Windows Python Launcher).
/// 4. `python3`.
/// 5. `python`.
pub fn find_python() -> String {
    if let Ok(val) = std::env::var("JOBHUNTER_PYTHON") {
        return val;
    }

    // Try the venv relative to the project root.
    let root = project_root_from_env();
    let venv_python = root.join(".venv").join("Scripts").join("python.exe");
    if venv_python.exists() {
        return venv_python.to_string_lossy().into_owned();
    }

    // Fallback candidates.
    for candidate in &["py", "python3", "python"] {
        if which_exists(candidate) {
            return candidate.to_string();
        }
    }

    "python".to_string()
}

/// Returns the project root.
///
/// Uses `JOBHUNTER_ROOT` env var if set; otherwise the current working
/// directory when the Tauri app is started (typically the project root in dev).
pub fn project_root_from_env() -> std::path::PathBuf {
    if let Ok(val) = std::env::var("JOBHUNTER_ROOT") {
        return std::path::PathBuf::from(val);
    }
    std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."))
}

fn which_exists(cmd: &str) -> bool {
    Command::new(cmd)
        .arg("--version")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

// ---------------------------------------------------------------------------
// Tauri command
// ---------------------------------------------------------------------------

/// Spawn the Python sidecar, stream progress events back to the frontend, and
/// return the final scored-job list as JSON.
///
/// The caller (Vue frontend, C-032) receives progress events via the Tauri
/// event `pipeline-progress` and the final array via the command's return
/// value.
#[tauri::command]
async fn run_pipeline(
    app: tauri::AppHandle,
    profile: String,
    provider: Option<String>,
) -> Result<serde_json::Value, String> {
    let python = find_python();
    let project_root = project_root_from_env();

    let request = serde_json::json!({
        "command": "run_pipeline",
        "args": {
            "profile": profile,
            "provider": provider,
        }
    });
    let request_line = format!("{}\n", request);

    let mut child = Command::new(&python)
        .args(["-m", "ui.cli.sidecar"])
        .current_dir(&project_root)
        .env("PYTHONPATH", project_root.to_string_lossy().as_ref())
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit()) // Python logs pass through to the Tauri process stderr
        .spawn()
        .map_err(|e| format!("failed to spawn sidecar ({python}): {e}"))?;

    // Write the request and close stdin so the sidecar knows there's no more input.
    if let Some(mut stdin) = child.stdin.take() {
        stdin
            .write_all(request_line.as_bytes())
            .map_err(|e| format!("stdin write error: {e}"))?;
    }

    let stdout = child
        .stdout
        .take()
        .ok_or("sidecar stdout unavailable")?;
    let reader = BufReader::new(stdout);

    let mut result_value: Option<serde_json::Value> = None;

    for line in reader.lines() {
        let line = line.map_err(|e| format!("stdout read error: {e}"))?;
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        let event: serde_json::Value = serde_json::from_str(trimmed)
            .map_err(|e| format!("invalid JSON from sidecar: {e} | line: {trimmed}"))?;

        match event["type"].as_str() {
            Some("progress") => {
                // Forward to the Vue frontend as a Tauri event.
                let _ = app.emit("pipeline-progress", &event);
            }
            Some("result") => {
                result_value = Some(event["data"].clone());
            }
            Some("error") => {
                let msg = event["message"].as_str().unwrap_or("unknown sidecar error");
                return Err(msg.to_string());
            }
            _ => {}
        }
    }

    child
        .wait()
        .map_err(|e| format!("sidecar wait error: {e}"))?;

    result_value.ok_or_else(|| "sidecar produced no result event".to_string())
}

// ---------------------------------------------------------------------------
// App entry point
// ---------------------------------------------------------------------------

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![run_pipeline])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
