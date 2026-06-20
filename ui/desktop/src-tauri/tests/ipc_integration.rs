/// C-031 — Rust integration test for the Python sidecar IPC contract (SDD §11.1).
///
/// Spawns `python -m ui.cli.sidecar` against an offline project (stub
/// provider + MockConnector + fixture jobs), sends a `run_pipeline` request,
/// and asserts it receives at least one progress event followed by a final
/// result event.  This test does NOT start the Tauri runtime; it exercises
/// the IPC protocol directly so it runs on any machine with Python installed.
use std::io::{BufRead, BufReader, Write};
use std::process::{Command, Stdio};

const STUB_PROVIDER: &str = r#"
from core.ai_providers.base_provider import BaseAIProvider
from core.models.search_criteria import SearchCriteria


class RustTestStubProvider(BaseAIProvider):
    name = "rust_test_stub"
    auth_methods = ("none",)
    supports_local = True

    async def generate_criteria(self, profile):
        return SearchCriteria(
            keywords=("rust",), min_score_threshold=40, raw_profile=profile
        )

    async def score_jobs(self, jobs, criteria):
        return [
            job.model_copy(update={"score": 91, "match_reason": "rust test pass"})
            for job in jobs
        ]
"#;

const FIXTURE_JOBS: &str = r#"[
  {
    "id": "rust-ipc-job",
    "title": "Rust Systems Engineer",
    "company": "Ferris Corp",
    "url": "https://example.test/rust-ipc-job",
    "location": "Remote",
    "description": "Rust async service development."
  }
]"#;

const CONFIG: &str = r#"
ai:
  provider: rust_test_stub
  model: stub
profile:
  input: text
connectors:
  mock:
    enabled: true
    fixture_path: fixtures/jobs.json
output:
  format: csv
  directory: output/
"#;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn find_python() -> String {
    // Prefer the JOBHUNTER_PYTHON env var (set in CI or dev shell).
    if let Ok(val) = std::env::var("JOBHUNTER_PYTHON") {
        return val;
    }
    // Try the project venv.
    let venv = project_root().join(".venv").join("Scripts").join("python.exe");
    if venv.exists() {
        return venv.to_string_lossy().into_owned();
    }
    // Fallback to system Python.
    "python".to_string()
}

/// Returns the project root (3 levels above CARGO_MANIFEST_DIR which is
/// `ui/desktop/src-tauri`).
fn project_root() -> std::path::PathBuf {
    let manifest = env!("CARGO_MANIFEST_DIR");
    std::path::Path::new(manifest)
        .ancestors()
        .nth(3)
        .expect("cannot navigate to project root from CARGO_MANIFEST_DIR")
        .to_path_buf()
}

fn setup_project(dir: &std::path::Path) {
    std::fs::create_dir_all(dir.join("ai_providers")).unwrap();
    std::fs::write(
        dir.join("ai_providers").join("rust_test_stub.py"),
        STUB_PROVIDER,
    )
    .unwrap();
    std::fs::create_dir_all(dir.join("fixtures")).unwrap();
    std::fs::write(dir.join("fixtures").join("jobs.json"), FIXTURE_JOBS).unwrap();
    std::fs::create_dir_all(dir.join("output")).unwrap();
    std::fs::write(dir.join("config.yaml"), CONFIG).unwrap();
}

// ---------------------------------------------------------------------------
// Test
// ---------------------------------------------------------------------------

#[test]
fn test_sidecar_run_pipeline_round_trip() {
    let tmp = tempfile::tempdir().expect("failed to create temp dir");
    let root = tmp.path();
    setup_project(root);

    let python = find_python();
    let project_root = project_root();

    let request = serde_json::json!({
        "command": "run_pipeline",
        "args": { "profile": "Senior Rust developer seeking remote work" }
    });
    let request_line = format!("{}\n", request);

    let mut child = Command::new(&python)
        .args(["-m", "ui.cli.sidecar"])
        .current_dir(root)
        .env("PYTHONPATH", project_root.to_string_lossy().as_ref())
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit())
        .spawn()
        .unwrap_or_else(|e| panic!("failed to spawn sidecar ({python}): {e}"));

    if let Some(mut stdin) = child.stdin.take() {
        stdin
            .write_all(request_line.as_bytes())
            .expect("stdin write failed");
    }

    let stdout = child.stdout.take().expect("stdout unavailable");
    let reader = BufReader::new(stdout);

    let mut progress_events: Vec<serde_json::Value> = vec![];
    let mut result_event: Option<serde_json::Value> = None;

    for line in reader.lines() {
        let line = line.expect("stdout read error");
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let event: serde_json::Value =
            serde_json::from_str(trimmed).unwrap_or_else(|e| {
                panic!("invalid JSON from sidecar: {e}\nline: {trimmed}")
            });

        match event["type"].as_str() {
            Some("progress") => progress_events.push(event),
            Some("result") => result_event = Some(event),
            Some("error") => panic!(
                "sidecar returned error: {}",
                event["message"].as_str().unwrap_or("?")
            ),
            _ => {}
        }
    }

    let status = child.wait().expect("wait failed");
    assert!(status.success(), "sidecar exited with {status}");

    // --- assertions ---

    assert!(
        !progress_events.is_empty(),
        "expected at least one progress event; got none"
    );

    for ev in &progress_events {
        assert!(ev["stage"].is_string(), "progress event missing 'stage': {ev}");
        assert!(ev["state"].is_string(), "progress event missing 'state': {ev}");
        assert!(ev["run_id"].is_string(), "progress event missing 'run_id': {ev}");
    }

    let result = result_event.expect("no result event received");
    let data = result["data"].as_array().expect("result.data is not an array");
    assert!(!data.is_empty(), "result.data is empty");

    let job = &data[0];
    assert_eq!(job["score"], 91, "unexpected score: {job}");
    assert_eq!(
        job["match_reason"].as_str().unwrap_or(""),
        "rust test pass"
    );
}
