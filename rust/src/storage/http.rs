use std::collections::BTreeMap;
use std::fs::File;
use std::io::Read;

use std::ffi::CStr;
use std::os::raw::c_char;

use base64;
use reqwest;

use super::singlefile::split_collection;
use super::Storage;
use errors::*;

use item::Item;

type ItemCache = BTreeMap<String, (Item, String)>;

#[derive(Clone, Serialize, Deserialize)]
pub struct Auth {
    username: String,
    password: String,
}

/// Wrapper around Client.execute to enable logging
#[inline]
pub fn send_request(
    client: &reqwest::Client,
    request: reqwest::Request,
) -> Fallible<reqwest::Response> {
    debug!("> {} {}", request.method(), request.url());
    for (name, value) in request.headers().iter() {
        debug!("> {}: {:?}", name, value);
    }
    debug!("> {:?}", request.body());
    debug!("> ---");
    let response = client.execute(request)?;
    debug!("< {:?}", response.status());
    for (name, value) in response.headers().iter() {
        debug!("< {}: {:?}", name, value);
    }
    Ok(response)
}

#[derive(Clone, Serialize, Deserialize)]
pub struct HttpConfig {
    #[serde(flatten)]
    pub auth: Option<Auth>,
    pub useragent: Option<String>,
    pub verify_cert: Option<String>,
    pub auth_cert: Option<String>,
    pub auth_cert_password: Option<String>,
}

impl HttpConfig {
    pub fn into_connection(self) -> Fallible<reqwest::ClientBuilder> {
        use reqwest::header;
        use reqwest::header::{HeaderMap, HeaderValue};

        let mut headers = HeaderMap::new();

        if let Some(auth) = self.auth {
            headers.insert(
                header::AUTHORIZATION,
                // Base64-encoded strings cannot contain invalid characters, so Err should never be
                // returned.
                HeaderValue::from_str(&format!(
                    "Basic {}",
                    base64::encode(&format!("{}:{}", auth.username, auth.password))
                ))
                .unwrap(),
            );
        }

        let user_agent_header = self
            .useragent
            .as_ref()
            .and_then(|s| HeaderValue::from_str(&s).ok())
            .unwrap_or_else(|| HeaderValue::from_static("vdirsyncer/0.17.0"));
        headers.insert(header::USER_AGENT, user_agent_header);

        let mut client = reqwest::Client::builder();
        client = client.default_headers(headers);

        if let Some(verify_cert) = self.verify_cert {
            let mut buf = Vec::new();
            File::open(verify_cert)?.read_to_end(&mut buf)?;
            let cert = reqwest::Certificate::from_pem(&buf)?;
            client = client.add_root_certificate(cert);
        }

        if let Some(auth_cert) = self.auth_cert {
            let mut buf = Vec::new();
            File::open(auth_cert)?.read_to_end(&mut buf)?;
            let cert = reqwest::Identity::from_pkcs12_der(
                &buf,
                self.auth_cert_password.as_ref().map(|x| &**x).unwrap_or(""),
            )?;
            client = client.identity(cert);
        }

        Ok(client)
    }
}

pub struct HttpStorage {
    url: String,
    // href -> (item, etag)
    items_cache: Option<ItemCache>,
    http_config: HttpConfig,
}

impl HttpStorage {
    pub fn new(url: String, http_config: HttpConfig) -> Self {
        HttpStorage {
            url,
            items_cache: None,
            http_config,
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
        let client = self.http_config.clone().into_connection()?.build()?;

        let mut response = handle_http_error(&self.url, client.get(&self.url).send()?)?;
        let s = response.text()?;

        let mut new_cache = BTreeMap::new();
        for component in split_collection(&s)? {
            let mut item = Item::from_component(component);
            item = item.with_uid(&item.get_hash()?)?;
            let ident = item.get_ident()?.to_owned();
            let hash = item.get_hash()?.to_owned();
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
            None => Err(Error::ItemNotFound {
                href: href.to_owned(),
            })?,
        }
    }

    fn upload(&mut self, _item: Item) -> Fallible<(String, String)> {
        Err(Error::ReadOnly)?
    }

    fn update(&mut self, _href: &str, _item: Item, _etag: &str) -> Fallible<String> {
        Err(Error::ReadOnly)?
    }

    fn delete(&mut self, _href: &str, _etag: &str) -> Fallible<()> {
        Err(Error::ReadOnly)?
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
        auth_cert_password: *const c_char,
    ) -> *mut Box<Storage> {
        let url = CStr::from_ptr(url);

        Box::into_raw(Box::new(Box::new(HttpStorage::new(
            url.to_str().unwrap().to_owned(),
            init_http_config(
                username,
                password,
                useragent,
                verify_cert,
                auth_cert,
                auth_cert_password,
            ),
        ))))
    }
}

pub fn handle_http_error(href: &str, mut r: reqwest::Response) -> Fallible<reqwest::Response> {
    if !r.status().is_success() {
        debug!("< Error response, dumping body:");
        debug!("< {:?}", r.text());
    }

    match r.status() {
        reqwest::StatusCode::NOT_FOUND => Err(Error::ItemNotFound {
            href: href.to_owned(),
        })?,
        reqwest::StatusCode::UNSUPPORTED_MEDIA_TYPE => Err(Error::UnsupportedVobject {
            href: href.to_owned(),
        })?,
        _ => Ok(r.error_for_status()?),
    }
}

pub unsafe fn init_http_config(
    username: *const c_char,
    password: *const c_char,
    useragent: *const c_char,
    verify_cert: *const c_char,
    auth_cert: *const c_char,
    auth_cert_password: *const c_char,
) -> HttpConfig {
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
    let auth_cert_password = CStr::from_ptr(auth_cert_password);
    let auth_cert_password_dec = auth_cert_password.to_str().unwrap();

    let auth = if !username_dec.is_empty() && !password_dec.is_empty() {
        Some(Auth {
            username: username_dec.to_owned(),
            password: password_dec.to_owned(),
        })
    } else {
        None
    };

    HttpConfig {
        auth,
        useragent: if useragent_dec.is_empty() {
            None
        } else {
            Some(useragent_dec.to_owned())
        },
        verify_cert: if verify_cert_dec.is_empty() {
            None
        } else {
            Some(verify_cert_dec.to_owned())
        },
        auth_cert: if auth_cert_dec.is_empty() {
            None
        } else {
            Some(auth_cert_dec.to_owned())
        },
        auth_cert_password: if auth_cert_password_dec.is_empty() {
            None
        } else {
            Some(auth_cert_password_dec.to_owned())
        },
    }
}
