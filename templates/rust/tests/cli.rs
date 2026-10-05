//! Integration test: the binary greets the name it is given.

use std::process::Command;

#[test]
fn binary_greets_its_argument() {
    let out = Command::new(env!("CARGO_BIN_EXE_example"))
        .arg("pack")
        .output()
        .expect("the example binary runs");
    assert!(out.status.success());
    assert_eq!(String::from_utf8_lossy(&out.stdout), "Hello, pack!\n");
}
