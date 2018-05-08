mod parser;

use chrono;

use std::io::{Read,BufReader};
use std::collections::BTreeSet;

use reqwest;
use reqwest::header::{ContentType,ETag};
use quick_xml;
use url::Url;

use super::Storage;
use errors::*;
use super::http::{HttpConfig,handle_http_error};

use item::Item;

#[inline]
fn propfind() -> reqwest::Method {
    reqwest::Method::Extension("PROPFIND".to_owned())
}

struct DavStorage {
    pub url: String,
    pub http_config: HttpConfig,
    pub http: Option<reqwest::Client>
}

impl DavStorage {
    pub fn get_http(&mut self) -> Fallible<reqwest::Client> {
        if let Some(ref http) = self.http {
            return Ok(http.clone());
        }
        let client = self.http_config.clone().into_connection()?.build()?;
        self.http = Some(client.clone());
        Ok(client)
    }

    pub fn get(&mut self, href: &str) -> Fallible<(Item, String)> {
        let base = Url::parse(&self.url)?;
        let url = base.join(href)?;
        if href != url.path() {
            Err(Error::ItemNotFound { href: href.to_owned() })?;
        }

        let mut response = handle_http_error(href, self.get_http()?.get(url).send()?)?;
        let mut s = String::new();
        response.read_to_string(&mut s)?;
        let etag = match response.headers().get::<ETag>() {
            Some(x) => format!("\"{}\"", x.tag()),
            None => Err(DavError::EtagNotFound)?
        };
        Ok((Item::from_raw(s), etag))
    }

    pub fn list<'a>(&'a mut self, mimetype_contains: &'a str)
        -> Fallible<Box<Iterator<Item = (String, String)> + 'a>> {
        let response = self.get_http()?
            .request(propfind(), &self.url)
            .header(ContentType::xml())
            .body(r#"<?xml version="1.0" encoding="utf-8" ?>
                <D:propfind xmlns:D="DAV:">
                    <D:prop>
                        <D:resourcetype/>
                        <D:getcontenttype/>
                        <D:getetag/>
                    </D:prop>
                </D:propfind>"#)
            .send()?.error_for_status()?;
        let buf_reader = BufReader::new(response);
        let xml_reader = quick_xml::Reader::from_reader(buf_reader);

        let mut parser = parser::ListingParser::new(xml_reader);
        let base = Url::parse(&self.url)?;
        let mut seen_hrefs = BTreeSet::new();

        Ok(Box::new(parser
                    .get_all_responses()?
                    .into_iter()
                    .filter_map(move |response| {
                        if response.has_collection_tag { return None; }
                        if !response.mimetype?.contains(mimetype_contains) { return None; }

                        let href = base.join(&response.href?).ok()?.path().to_owned();

                        if seen_hrefs.contains(&href) { return None; }
                        seen_hrefs.insert(href.clone());
                        Some((href, response.etag?))
                    })))
    }
}

pub struct CarddavStorage {
    inner: DavStorage
}

impl CarddavStorage {
    pub fn new(
        url: String,
        http_config: HttpConfig
    ) -> Self {
        CarddavStorage {
            inner: DavStorage {
                url,
                http_config,
                http: None
            }
        }
    }
}

impl Storage for CarddavStorage {
    fn list<'a>(&'a mut self) -> Fallible<Box<Iterator<Item = (String, String)> + 'a>> {
        self.inner.list("vcard")
    }

    fn get(&mut self, href: &str) -> Fallible<(Item, String)> {
        self.inner.get(href)
    }

    fn upload(&mut self, _item: Item) -> Fallible<(String, String)> {
        panic!();
    }

    fn update(&mut self, _href: &str, _item: Item, _etag: &str) -> Fallible<String> {
        panic!();
    }

    fn delete(&mut self, _href: &str, _etag: &str) -> Fallible<()> {
        panic!();
    }
}

pub struct CaldavStorage {
    inner: DavStorage,
    start_date: Option<chrono::DateTime<chrono::Utc>>,
    end_date: Option<chrono::DateTime<chrono::Utc>>
}

impl CaldavStorage {
    pub fn new(
        url: String,
        http_config: HttpConfig,
        start_date: Option<chrono::DateTime<chrono::Utc>>,
        end_date: Option<chrono::DateTime<chrono::Utc>>,
    ) -> Self {
        CaldavStorage {
            inner: DavStorage {
                url,
                http_config,
                http: None,
            },
            start_date,
            end_date
        }
    }
}

impl Storage for CaldavStorage {
    fn list<'a>(&'a mut self) -> Fallible<Box<Iterator<Item = (String, String)> + 'a>> {
        // TODO: timeranges
        self.inner.list("text/calendar")
    }

    fn get(&mut self, href: &str) -> Fallible<(Item, String)> {
        self.inner.get(href)
    }

    fn upload(&mut self, _item: Item) -> Fallible<(String, String)> {
        panic!();
    }

    fn update(&mut self, _href: &str, _item: Item, _etag: &str) -> Fallible<String> {
        panic!();
    }

    fn delete(&mut self, _href: &str, _etag: &str) -> Fallible<()> {
        panic!();
    }
}

pub mod exports {
    use super::*;
    use super::super::http::init_http_config;

    #[derive(Debug, Fail, Shippai)]
    pub enum DavError {
        #[fail(display = "Server did not return etag.")]
        EtagNotFound
    }

    use std::ffi::CStr;
    use std::os::raw::c_char;

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_init_carddav(
        url: *const c_char,
        username: *const c_char,
        password: *const c_char,
        useragent: *const c_char,
        verify_cert: *const c_char,
        auth_cert: *const c_char,
    ) -> *mut Box<Storage> {
        let url = CStr::from_ptr(url);

        Box::into_raw(Box::new(Box::new(CarddavStorage::new(
            url.to_str().unwrap().to_owned(),
            init_http_config(
                username,
                password,
                useragent,
                verify_cert,
                auth_cert
            )
        ))))
    }

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_init_caldav(
        url: *const c_char,
        username: *const c_char,
        password: *const c_char,
        useragent: *const c_char,
        verify_cert: *const c_char,
        auth_cert: *const c_char,
        start_date: i64,
        end_date: i64
    ) -> *mut Box<Storage> {
        let url = CStr::from_ptr(url);

        let parse_date = |i| {
            if i > 0 {
                Some(chrono::DateTime::from_utc(
                    chrono::NaiveDateTime::from_timestamp(i, 0),
                    chrono::Utc
                ))
            } else {
                None
            }
        };

        Box::into_raw(Box::new(Box::new(CaldavStorage::new(
            url.to_str().unwrap().to_owned(),
            init_http_config(
                username,
                password,
                useragent,
                verify_cert,
                auth_cert
            ),
            parse_date(start_date),
            parse_date(end_date),
        ))))
    }
}

use exports::DavError;
