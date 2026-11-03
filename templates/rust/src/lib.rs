//! A vigOS Rust pack starter: rename `example` (see README.md) and replace
//! this with your crate.

/// Return a greeting for `name`.
///
/// Doctests run in the pack's `doctest` check and in `just test`:
///
/// ```
/// assert_eq!(example::greet("world"), "Hello, world!");
/// ```
pub fn greet(name: &str) -> String {
    format!("Hello, {name}!")
}

#[cfg(test)]
mod tests {
    use super::greet;

    #[test]
    fn greets_by_name() {
        assert_eq!(greet("vigOS"), "Hello, vigOS!");
    }
}
