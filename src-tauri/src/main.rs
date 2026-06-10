// Prevents an extra console window on Windows in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    ffi::OsString,
    fs::OpenOptions,
    io::{Read, Write},
    net::{TcpStream, ToSocketAddrs},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};
use tauri::Manager;

const GUI_HOST: &str = "127.0.0.1";
const GUI_PORT: u16 = 8765;
const DEFAULT_STARTUP_TIMEOUT_SECS: u64 = 60;

struct BackendProcess(Mutex<Option<Child>>);

fn main() {
    let startup_timeout = startup_timeout_from_env();
    tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(None)))
        .plugin(tauri_plugin_dialog::init())
        .setup(move |app| {
            let launch_context = resolve_launch_context(app);
            if is_gui_reachable() {
                return Ok(());
            }
            match spawn_python_gui(&launch_context) {
                Ok(child) => {
                    *app.state::<BackendProcess>().0.lock().expect("backend lock poisoned") =
                        Some(child);
                    if let Err(error) = wait_for_gui(startup_timeout) {
                        eprintln!("{error}");
                        return Err(error);
                    }
                }
                Err(error) => {
                    eprintln!("Failed to start Event Face Finder backend: {error}");
                    return Err(error);
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::ExitRequested { .. } = event {
                if let Some(mut child) = app_handle
                    .state::<BackendProcess>()
                    .0
                    .lock()
                    .expect("backend lock poisoned")
                    .take()
                {
                    let _ = child.kill();
                    let _ = child.wait();
                }
            }
        });
}

fn startup_timeout_from_env() -> Duration {
    match std::env::var("EFF_STARTUP_TIMEOUT_SECS") {
        Ok(value) => value
            .parse::<u64>()
            .ok()
            .filter(|seconds| *seconds > 0)
            .map(Duration::from_secs)
            .unwrap_or_else(|| Duration::from_secs(DEFAULT_STARTUP_TIMEOUT_SECS)),
        Err(_) => Duration::from_secs(DEFAULT_STARTUP_TIMEOUT_SECS),
    }
}

struct LaunchContext {
    source_dir: PathBuf,
    working_dir: PathBuf,
}

fn spawn_python_gui(launch_context: &LaunchContext) -> Result<Child, tauri::Error> {
    let python = python_executable(&launch_context.working_dir);
    let log_file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(launch_context.working_dir.join("desktop-backend.log"))
        .map_err(|error| tauri::Error::Anyhow(anyhow::Error::from(error)))?;
    let error_log = log_file
        .try_clone()
        .map_err(|error| tauri::Error::Anyhow(anyhow::Error::from(error)))?;

    Command::new(python)
        .arg("-c")
        .arg(format!(
            "from event_face_finder.gui import run_gui; run_gui({GUI_HOST:?}, {GUI_PORT}, False)"
        ))
        .current_dir(&launch_context.working_dir)
        .env("PYTHONPATH", python_path_env(&launch_context.source_dir))
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .stdin(Stdio::null())
        .stdout(Stdio::from(log_file))
        .stderr(Stdio::from(error_log))
        .spawn()
        .map_err(|error| tauri::Error::Anyhow(anyhow::Error::from(error)))
}

fn python_executable(project_root: &Path) -> PathBuf {
    if let Ok(value) = std::env::var("EFF_PYTHON") {
        return PathBuf::from(value);
    }

    let unix_venv = project_root.join(".venv/bin/python");
    if unix_venv.is_file() {
        return unix_venv;
    }

    let windows_venv = project_root.join(".venv/Scripts/python.exe");
    if windows_venv.is_file() {
        return windows_venv;
    }

    PathBuf::from("python3")
}

fn resolve_launch_context(app: &tauri::App) -> LaunchContext {
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let project_root = resolve_project_root(&cwd);
    if project_root.join("event_face_finder").is_dir() {
        return LaunchContext {
            source_dir: project_root.clone(),
            working_dir: project_root,
        };
    }

    let resource_source = app
        .path()
        .resource_dir()
        .ok()
        .and_then(|path| python_source_dir_from_resource(&path));
    if let Some(source_dir) = resource_source {
        let working_dir = user_workspace_dir();
        let _ = std::fs::create_dir_all(&working_dir);
        return LaunchContext {
            source_dir,
            working_dir,
        };
    }

    LaunchContext {
        source_dir: project_root.clone(),
        working_dir: project_root,
    }
}

fn resolve_project_root(cwd: &Path) -> PathBuf {
    if cwd.file_name().is_some_and(|name| name == "src-tauri") {
        return cwd.parent().unwrap_or(&cwd).to_path_buf();
    }
    cwd.to_path_buf()
}

fn python_source_dir_from_resource(resource_dir: &Path) -> Option<PathBuf> {
    [resource_dir.to_path_buf(), resource_dir.join("_up_")]
        .into_iter()
        .find(|path| path.join("event_face_finder").is_dir())
}

fn user_workspace_dir() -> PathBuf {
    home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("Documents")
        .join("Event Face Finder")
}

fn home_dir() -> Option<PathBuf> {
    std::env::var_os("HOME")
        .or_else(|| std::env::var_os("USERPROFILE"))
        .map(PathBuf::from)
}

fn python_path_env(source_dir: &Path) -> OsString {
    let mut paths = vec![source_dir.to_path_buf()];
    if let Some(existing) = std::env::var_os("PYTHONPATH") {
        paths.extend(std::env::split_paths(&existing));
    }
    std::env::join_paths(paths).unwrap_or_else(|_| source_dir.as_os_str().to_os_string())
}

fn wait_for_gui(timeout: Duration) -> Result<(), tauri::Error> {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if is_gui_reachable() {
            return Ok(());
        }
        thread::sleep(Duration::from_millis(250));
    }

    Err(tauri::Error::Anyhow(anyhow::anyhow!(
        "Timed out waiting for the local Event Face Finder GUI server."
    )))
}

fn is_gui_reachable() -> bool {
    let Some(addr) = (GUI_HOST, GUI_PORT)
        .to_socket_addrs()
        .ok()
        .and_then(|mut addrs| addrs.next())
    else {
        return false;
    };

    let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(250)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));

    let request = format!(
        "GET /api/status HTTP/1.1\r\nHost: {GUI_HOST}:{GUI_PORT}\r\nConnection: close\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }

    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }
    // The body of /api/status is JSON like {"status":"idle",...}. Confirm the
    // endpoint is actually ours (and not another local service on the same
    // port) by checking both the status line and the expected JSON key.
    let header_end = match response.find("\r\n\r\n") {
        Some(index) => index,
        None => return false,
    };
    let headers = &response[..header_end];
    let body = &response[header_end + 4..];
    let status_ok = headers.starts_with("HTTP/1.1 200") || headers.starts_with("HTTP/1.0 200");
    status_ok && body.contains("\"status\"")
}
