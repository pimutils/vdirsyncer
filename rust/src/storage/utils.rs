use uuid::Uuid;

fn is_href_safe(ident: &str) -> bool {
    for c in ident.chars() {
        match c {
            '_' | '.' | '-' | '+' => (),
            _ if c.is_alphanumeric() => (),
            _ => return false,
        }
    }
    true
}

pub fn generate_href(ident: &str) -> String {
    if is_href_safe(ident) {
        ident.to_owned()
    } else {
        random_href()
    }
}

pub fn random_href() -> String {
    format!("{}", Uuid::new_v4())
}
