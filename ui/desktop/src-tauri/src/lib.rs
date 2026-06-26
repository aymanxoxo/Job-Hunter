// JobHunter desktop — Tauri v2 shell + Python sidecar IPC (C-031, SDD §11.1).
//
// The Python core runs as a child process.  Rust writes one JSON request to
// its stdin and reads newline-delimited JSON events from its stdout:
//   - {"type":"progress", ...}  forwarded as Tauri events to the frontend
//   - {"type":"result",  ...}  returned as the command's Ok value
//   - {"type":"export",  ...}  returned as configured export output paths
//   - {"type":"error",  ...}  turned into an Err return
//
// All Python logs go to the child's stderr and are NOT read here, so they
// never corrupt the JSON stream (SDD §11.1 rule: stdout is the IPC channel).

use std::process::{Command, Stdio};
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tauri::Emitter;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::Command as TokioCommand;
use tokio::time::timeout;

const SIDECAR_TIMEOUT_SECONDS: u64 = 15 * 60;

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
/// 3. `.venv/bin/python3` or `.venv/bin/python` relative to the same root.
/// 4. `py` (Windows Python Launcher).
/// 5. `python3`.
/// 6. `python`.
pub fn find_python() -> String {
    if let Ok(val) = std::env::var("JOBHUNTER_PYTHON") {
        return val;
    }

    // Try the venv relative to the project root.
    let root = project_root_from_env();
    let venv_candidates = [
        root.join(".venv").join("Scripts").join("python.exe"),
        root.join(".venv").join("bin").join("python3"),
        root.join(".venv").join("bin").join("python"),
    ];
    for candidate in venv_candidates {
        if candidate.exists() {
            return candidate.to_string_lossy().into_owned();
        }
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

async fn call_sidecar(
    app: tauri::AppHandle,
    command: &str,
    args: serde_json::Value,
    result_type: &str,
) -> Result<serde_json::Value, String> {
    timeout(
        Duration::from_secs(SIDECAR_TIMEOUT_SECONDS),
        call_sidecar_inner(app, command, args, result_type),
    )
    .await
    .map_err(|_| format!("sidecar timed out after {SIDECAR_TIMEOUT_SECONDS} seconds"))?
}

pub fn parse_sidecar_event(trimmed: &str) -> Result<serde_json::Value, String> {
    serde_json::from_str(trimmed)
        .map_err(|e| format!("invalid JSON from sidecar: {e}; stdout line was not protocol JSON"))
}

async fn call_sidecar_inner(
    app: tauri::AppHandle,
    command: &str,
    args: serde_json::Value,
    result_type: &str,
) -> Result<serde_json::Value, String> {
    let python = find_python();
    let project_root = project_root_from_env();

    let request = serde_json::json!({ "command": command, "args": args });
    let request_line = format!("{}\n", request);

    let mut child = TokioCommand::new(&python)
        .args(["-m", "ui.cli.sidecar"])
        .current_dir(&project_root)
        .env("PYTHONPATH", project_root.to_string_lossy().as_ref())
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit()) // Python logs pass through to the Tauri process stderr
        .kill_on_drop(true)
        .spawn()
        .map_err(|e| format!("failed to spawn sidecar ({python}): {e}"))?;

    // Write the request and close stdin so the sidecar knows there's no more input.
    if let Some(mut stdin) = child.stdin.take() {
        stdin
            .write_all(request_line.as_bytes())
            .await
            .map_err(|e| format!("stdin write error: {e}"))?;
        stdin
            .shutdown()
            .await
            .map_err(|e| format!("stdin close error: {e}"))?;
    }

    let stdout = child.stdout.take().ok_or("sidecar stdout unavailable")?;
    let reader = BufReader::new(stdout);
    let mut lines = reader.lines();

    let mut result_value: Option<serde_json::Value> = None;

    while let Some(line) = lines
        .next_line()
        .await
        .map_err(|e| format!("stdout read error: {e}"))?
    {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        let event = parse_sidecar_event(trimmed)?;

        match event["type"].as_str() {
            Some("progress") => {
                // Forward to the Vue frontend as a Tauri event.
                let _ = app.emit("pipeline-progress", &event);
            }
            Some(kind) if kind == result_type => {
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
        .await
        .map_err(|e| format!("sidecar wait error: {e}"))?;

    result_value.ok_or_else(|| format!("sidecar produced no {result_type} event"))
}

async fn call_profile_sidecar(
    app: tauri::AppHandle,
    command: &str,
    profile: String,
    provider: Option<String>,
    connector_overrides: Option<serde_json::Value>,
    result_type: &str,
) -> Result<serde_json::Value, String> {
    let mut args = serde_json::json!({
        "profile": profile,
        "provider": provider,
    });
    if let Some(overrides) = connector_overrides {
        args["connector_overrides"] = overrides;
    }
    call_sidecar(app, command, args, result_type).await
}

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
    connector_overrides: Option<serde_json::Value>,
) -> Result<serde_json::Value, String> {
    call_profile_sidecar(
        app,
        "run_pipeline",
        profile,
        provider,
        connector_overrides,
        "result",
    )
    .await
}

/// Invoke provider-backed criteria generation through the same Python sidecar
/// boundary used by full pipeline runs.
#[tauri::command]
async fn generate_criteria(
    app: tauri::AppHandle,
    profile: String,
    provider: Option<String>,
) -> Result<serde_json::Value, String> {
    call_profile_sidecar(
        app,
        "generate_criteria",
        profile,
        provider,
        None,
        "criteria",
    )
    .await
}

/// Write the provided result rows through the Python exporter and return the
/// configured output paths.
#[tauri::command]
async fn export_results(
    app: tauri::AppHandle,
    jobs: serde_json::Value,
) -> Result<serde_json::Value, String> {
    call_sidecar(
        app,
        "export_results",
        serde_json::json!({ "jobs": jobs }),
        "export",
    )
    .await
}

// ---------------------------------------------------------------------------
// App entry point
// ---------------------------------------------------------------------------

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            run_pipeline,
            generate_criteria,
            export_results
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
