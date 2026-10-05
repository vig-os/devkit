//! Command-line entry point for the `example` starter.

fn main() {
    let name = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "world".to_owned());
    println!("{}", example::greet(&name));
}
