use std::collections::BTreeMap;
use std::fs::File;
use std::io::Read;

use reqwest;

use super::Storage;
use errors::*;
use super::singlefile::split_collection;

use item::Item;

type ItemCache = BTreeMap<String, (Item, String)>;
type Username = String;
type Password = String;
type Auth = (Username, Password);

fn get_http_connection(
    auth: Option<Auth>,
    useragent: Option<String>,
    verify_cert: Option<String>,
    _auth_cert: Option<String>,
) -> Fallible<reqwest::ClientBuilder> {
    let mut headers = reqwest::header::Headers::new();

    if let Some((username, password)) = auth {
        headers.set(reqwest::header::Authorization(reqwest::header::Basic {
            username,
            password: Some(password),
        }));
    }

    if let Some(useragent) = useragent {
        headers.set(reqwest::header::UserAgent::new(useragent));
    }

    let mut client = reqwest::Client::builder();
    client.default_headers(headers);

    if let Some(verify_cert) = verify_cert {
        let mut buf = Vec::new();
        File::open(verify_cert)?.read_to_end(&mut buf)?;
        let cert = reqwest::Certificate::from_pem(&buf)?;
        client.add_root_certificate(cert);
    }

    // TODO: auth_cert https://github.com/sfackler/rust-native-tls/issues/27
    Ok(client)
}

pub struct HttpStorage {
    url: String,
    auth: Option<Auth>,
    // href -> (item, etag)
    items_cache: Option<ItemCache>,
    useragent: Option<String>,
    verify_cert: Option<String>,
    auth_cert: Option<String>,
}

impl HttpStorage {
    pub fn new(
        url: String,
        auth: Option<Auth>,
        useragent: Option<String>,
        verify_cert: Option<String>,
        auth_cert: Option<String>,
    ) -> Self {
        HttpStorage {
            url,
            auth,
            items_cache: None,
            useragent,
            verify_cert,
            auth_cert,
        }
    }

    fn get_items(&mut self) -> Fallible<&mut ItemCache> {
        if self.items_cache.is_none() {
            self.list()?;
        }
        Ok(self.items_cache.as_mut().unwrap())
    }
}

impl Storage for HttpStorage {
    fn list<'a>(&'a mut self) -> Fallible<Box<Iterator<Item = (String, String)> + 'a>> {
        let client = get_http_connection(
            self.auth.clone(),
            self.useragent.clone(),
            self.verify_cert.clone(),
            self.auth_cert.clone(),
        )?.build()?;

        let mut response = client.get(&self.url).send()?.error_for_status()?;
        let s = response.text()?;

        let mut new_cache = BTreeMap::new();
        for component in split_collection(&s)? {
            let mut item = Item::from_component(component);
            item = item.with_uid(&item.get_hash()?)?;
            let ident = item.get_ident()?;
            let hash = item.get_hash()?;
            new_cache.insert(ident, (item, hash));
        }

        self.items_cache = Some(new_cache);
        Ok(Box::new(self.items_cache.as_ref().unwrap().iter().map(
            |(href, &(_, ref etag))| (href.clone(), etag.clone()),
        )))
    }

    fn get(&mut self, href: &str) -> Fallible<(Item, String)> {
        match self.get_items()?.get(href) {
            Some(&(ref href, ref etag)) => Ok((href.clone(), etag.clone())),
            None => Err(ItemNotFound {
                href: href.to_owned(),
            })?,
        }
    }

    fn upload(&mut self, _item: Item) -> Fallible<(String, String)> {
        Err(ReadOnly)?
    }

    fn update(&mut self, _href: &str, _item: Item, _etag: &str) -> Fallible<String> {
        Err(ReadOnly)?
    }

    fn delete(&mut self, _href: &str, _etag: &str) -> Fallible<()> {
        Err(ReadOnly)?
    }
}

pub mod exports {
    use super::*;
    use std::ffi::CStr;
    use std::os::raw::c_char;

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_init_http(
        url: *const c_char,
        username: *const c_char,
        password: *const c_char,
        useragent: *const c_char,
        verify_cert: *const c_char,
        auth_cert: *const c_char,
    ) -> *mut Box<Storage> {
        let url = CStr::from_ptr(url);

        let username = CStr::from_ptr(username);
        let password = CStr::from_ptr(password);
        let username_dec = username.to_str().unwrap();
        let password_dec = password.to_str().unwrap();

        let useragent = CStr::from_ptr(useragent);
        let useragent_dec = useragent.to_str().unwrap();
        let verify_cert = CStr::from_ptr(verify_cert);
        let verify_cert_dec = verify_cert.to_str().unwrap();
        let auth_cert = CStr::from_ptr(auth_cert);
        let auth_cert_dec = auth_cert.to_str().unwrap();

        let auth = if !username_dec.is_empty() && !password_dec.is_empty() {
            Some((username_dec.to_owned(), password_dec.to_owned()))
        } else {
            None
        };

        Box::into_raw(Box::new(Box::new(HttpStorage::new(
            url.to_str().unwrap().to_owned(),
            auth,
            if useragent_dec.is_empty() {
                None
            } else {
                Some(useragent_dec.to_owned())
            },
            if verify_cert_dec.is_empty() {
                None
            } else {
                Some(verify_cert_dec.to_owned())
            },
            if auth_cert_dec.is_empty() {
                None
            } else {
                Some(auth_cert_dec.to_owned())
            },
        ))))
    }
}