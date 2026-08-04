use std::sync::Arc;
use super::{CommandOutput, TransactionErrorFilter};

pub fn stderr_contains<S:AsRef<str>+ ToString>(pattern:S) -> TransactionErrorFilter
{
    let p = pattern.to_string();
    Arc::new(move |output: &CommandOutput|
        {
            output.stderr.contains(&p)
        }
    )
}