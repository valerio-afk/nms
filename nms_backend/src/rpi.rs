use tokio::fs;

static  PATHS: &[&str] = &[
    "/sys/firmware/devicetree/base/model",
    "/proc/device-tree/model",
];
pub async fn raspberry_model() -> Option<String> {

    for path in PATHS {
        if let Ok(model) = fs::read_to_string(path).await
        {
            // Device tree strings are NUL-terminated.
            return Some(model.trim_matches(char::from(0)).trim().to_string());
        }
    }

    None
}

pub async  fn is_raspberry_pi() -> bool {
    raspberry_model()
        .await
        .as_deref()
        .is_some_and(|m| m.starts_with("Raspberry Pi"))
}