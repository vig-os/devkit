//! Consumer-matrix hello world (devkit #1762).

/// Return a greeting for `name`.
pub fn greet(name: &str) -> String {
    format!("Hello, {name}!")
}

#[cfg(test)]
mod tests {
    #[test]
    fn greet() {
        assert_eq!(super::greet("matrix"), "Hello, matrix!");
        // Proof for the matrix that `just test` really ran this suite.
        if let Ok(sentinel) = std::env::var("CONSUMER_MATRIX_SENTINEL") {
            std::fs::write(sentinel, "rust\n").unwrap();
        }
    }
}
