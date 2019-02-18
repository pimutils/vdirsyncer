mod caldav;
mod carddav;
pub mod google;
mod parser;

pub use self::caldav::CaldavStorage;
pub use self::carddav::CarddavStorage;

use std::collections::BTreeSet;
use std::fmt;
use std::io::{BufReader, Read};

use quick_xml;
use reqwest;
use reqwest::header;
use reqwest::header::{HeaderMap, HeaderValue};
use url::Url;

use super::http::{handle_http_error, send_request, HttpConfig};
use super::{normalize_meta_value, Metadata, Storage, StorageConfig};
use errors::*;

use item::Item;

#[derive(Debug, Clone, Copy)]
struct XmlTag(&'static str, &'static str); // tagname, namespace

impl fmt::Display for XmlTag {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "<{} xmlns=\"{}\"/>", self.0, self.1)
    }
}

mod dav_methods {
    use reqwest;
    #[inline]
    pub fn propfind() -> reqwest::Method {
        "PROPFIND".parse().unwrap()
    }

    #[inline]
    pub fn proppatch() -> reqwest::Method {
        "PROPPATCH".parse().unwrap()
    }

    #[inline]
    pub fn report() -> reqwest::Method {
        "REPORT".parse().unwrap()
    }

    #[inline]
    pub fn mkcol() -> reqwest::Method {
        "MKCOL".parse().unwrap()
    }
}

use self::dav_methods::*;

trait StorageType {
    fn tagname_and_namespace_for_meta_key(key: Metadata) -> Fallible<XmlTag>;

    fn well_known_path() -> &'static str;

    fn homeset_body() -> &'static str;

    fn get_homeset_url(response: &parser::Response) -> Option<&str>;

    fn is_valid_collection(response: &parser::Response) -> bool;

    fn collection_resource_type() -> XmlTag;

    fn collection_name_from_url(url: &Url) -> Option<String> {
        Some(
            url.path_segments()?
                .rev()
                .find(|x| !x.is_empty())?
                .to_owned(),
        )
    }
}

struct DavClient {
    pub url: String,
    pub http_config: HttpConfig,
    pub http: Option<reqwest::Client>,
}

impl DavClient {
    pub fn new(url: &str, http_config: HttpConfig) -> Self {
        DavClient {
            url: format!("{}/", url.trim_right_matches('/')),
            http_config,
            http: None,
        }
    }
}

impl DavClient {
    #[inline]
    pub fn get_http(&mut self) -> Fallible<reqwest::Client> {
        if let Some(ref http) = self.http {
            return Ok(http.clone());
        }
        let client = self.http_config.clone().into_connection()?.build()?;
        self.http = Some(client.clone());
        Ok(client)
    }

    #[inline]
    pub fn send_request(&mut self, request: reqwest::Request) -> Fallible<reqwest::Response> {
        let url = request.url().to_string();
        handle_http_error(&url, send_request(&self.get_http()?, request)?)
    }

    pub fn get(&mut self, href: &str) -> Fallible<(Item, String)> {
        let base = Url::parse(&self.url)?;
        let url = base.join(href)?;
        if href != url.path() {
            Err(Error::ItemNotFound {
                href: href.to_owned(),
            })?;
        }

        let request = self.get_http()?.get(url).build()?;
        let mut response = self.send_request(request)?;
        let mut s = String::new();
        response.read_to_string(&mut s)?;
        let etag = match response.headers().get(header::ETAG) {
            Some(x) => x.to_str().unwrap().to_owned(),
            None => Err(DavError::EtagNotFound)?,
        };
        Ok((Item::from_raw(s), etag))
    }

    pub fn list<'a>(
        &'a mut self,
        mimetype_contains: &'a str,
    ) -> Fallible<Box<Iterator<Item = (String, String)> + 'a>> {
        let mut headers = HeaderMap::new();
        headers.insert(
            header::CONTENT_TYPE,
            HeaderValue::from_static("application/xml"),
        );
        headers.insert("Depth", HeaderValue::from_static("1"));

        let request = self
            .get_http()?
            .request(propfind(), &self.url)
            .headers(headers)
            .body(
                r#"<?xml version="1.0" encoding="utf-8" ?>
                <D:propfind xmlns:D="DAV:">
                    <D:prop>
                        <D:resourcetype/>
                        <D:getcontenttype/>
                        <D:getetag/>
                    </D:prop>
                </D:propfind>"#,
            )
            .build()?;
        let response = self.send_request(request)?;
        self.parse_item_listing_response(response, mimetype_contains)
    }

    fn parse_item_listing_response<'a>(
        &'a mut self,
        response: reqwest::Response,
        mimetype_contains: &'a str,
    ) -> Fallible<Box<Iterator<Item = (String, String)> + 'a>> {
        let buf_reader = BufReader::new(response);
        let xml_reader = quick_xml::Reader::from_reader(buf_reader);

        let mut parser = parser::ListingParser::new(xml_reader);
        let base = Url::parse(&self.url)?;
        let mut seen_hrefs = BTreeSet::new();

        Ok(Box::new(
            parser
                .get_all_responses()?
                .into_iter()
                .filter_map(move |response| {
                    if response.is_collection || response.is_calendar || response.is_addressbook {
                        return None;
                    }
                    if !response.mimetype?.contains(mimetype_contains) {
                        return None;
                    }

                    let href = base.join(&response.href?).ok()?.path().to_owned();

                    if seen_hrefs.contains(&href) {
                        return None;
                    }
                    seen_hrefs.insert(href.clone());
                    Some((href, response.etag?))
                }),
        ))
    }

    fn put(
        &mut self,
        href: &str,
        item: &Item,
        mimetype: &str,
        etag: Option<&str>,
    ) -> Fallible<(String, String)> {
        let base = Url::parse(&self.url)?;
        let url = base.join(href)?;
        let mut request = self.get_http()?.request(reqwest::Method::PUT, url);
        request = request.header(
            header::CONTENT_TYPE,
            HeaderValue::from_str(mimetype).expect("Invalid mimetype"),
        );
        if let Some(etag) = etag {
            request = request.header(
                header::IF_MATCH,
                HeaderValue::from_str(&format!("\"{}\"", etag.trim_matches('"')))
                    .expect("Etag contained forbidden characters"),
            );
        } else {
            request = request.header(header::IF_NONE_MATCH, HeaderValue::from_static("*"));
        }

        let raw = item.get_raw();
        let response = send_request(&self.get_http()?, request.body(raw).build()?)?;

        match (etag, response.status()) {
            (Some(_), reqwest::StatusCode::PRECONDITION_FAILED) => Err(Error::WrongEtag {
                href: href.to_owned(),
            })?,
            (None, reqwest::StatusCode::PRECONDITION_FAILED) => Err(Error::ItemAlreadyExisting {
                href: href.to_owned(),
            })?,
            _ => (),
        }

        let response = assert_multistatus_success(handle_http_error(href, response)?)?;

        // The server may not return an etag under certain conditions:
        //
        //   An origin server MUST NOT send a validator header field (Section
        //   7.2), such as an ETag or Last-Modified field, in a successful
        //   response to PUT unless the request's representation data was saved
        //   without any transformation applied to the body (i.e., the
        //   resource's new representation data is identical to the
        //   representation data received in the PUT request) and the validator
        //   field value reflects the new representation.
        //
        // -- https://tools.ietf.org/html/rfc7231#section-4.3.4
        //
        // In such cases we return a constant etag. The next synchronization
        // will then detect an etag change and will download the new item.
        let etag = match response.headers().get(header::ETAG) {
            Some(x) => x.to_str().unwrap().to_owned(),
            None => Err(DavError::EtagNotFound)?,
        };
        Ok((response.url().path().to_owned(), etag))
    }

    fn delete(&mut self, href: &str, etag: &str) -> Fallible<()> {
        let base = Url::parse(&self.url)?;
        let url = base.join(href)?;
        let request = self
            .get_http()?
            .request(reqwest::Method::DELETE, url)
            .header(
                header::IF_MATCH,
                HeaderValue::from_str(&format!("\"{}\"", etag.trim_matches('"')))
                    .expect("Etag contained forbidden characters"),
            )
            .build()?;
        let response = send_request(&self.get_http()?, request)?;

        if response.status() == reqwest::StatusCode::PRECONDITION_FAILED {
            Err(Error::WrongEtag {
                href: href.to_owned(),
            })?;
        }

        assert_multistatus_success(handle_http_error(href, response)?)?;
        Ok(())
    }

    fn get_well_known_url<S: StorageType>(&mut self) -> Fallible<Url> {
        let url = Url::parse(&self.url)?;
        let request = self
            .get_http()?
            .get(url.join(S::well_known_path())?)
            .build()?;
        match self.send_request(request) {
            Ok(response) => Ok(response.url().clone()),
            Err(e) => {
                debug!("Failed to discover DAV through well-known URIs, just using configured URL as base");
                debug!("Error message: {:?}", e);
                Ok(url)
            }
        }
    }

    pub fn get_principal_url<S: StorageType>(&mut self) -> Fallible<Url> {
        let well_known_url = self.get_well_known_url::<S>()?;

        let mut headers = HeaderMap::new();
        headers.insert(
            header::CONTENT_TYPE,
            HeaderValue::from_static("application/xml"),
        );
        headers.insert("Depth", HeaderValue::from_static("0"));

        let request = self
            .get_http()?
            .request(propfind(), well_known_url)
            .headers(headers)
            .body(
                "<?xml version=\"1.0\" encoding=\"utf-8\" ?>\
                 <d:propfind xmlns:d=\"DAV:\">\
                 <d:prop>\
                 <d:current-user-principal />\
                 </d:prop>\
                 </d:propfind>",
            )
            .build()?;
        let response = self.send_request(request)?;

        let buf_reader = BufReader::new(response);
        let xml_reader = quick_xml::Reader::from_reader(buf_reader);
        let mut parser = parser::ListingParser::new(xml_reader);
        let base = Url::parse(&self.url)?;

        while let Some(response) = parser.next_response()? {
            if let Some(href) = response.current_user_principal {
                return Ok(base.join(&href)?);
            }
        }

        Err(DavError::NoPrincipalUrl)?
    }

    fn get_homeset_url<S: StorageType>(&mut self) -> Fallible<Url> {
        let base = Url::parse(&self.url)?;
        if base.path() != "/" {
            Ok(base)
        } else {
            let principal_url = self.get_principal_url::<S>()?;

            let mut headers = HeaderMap::new();
            headers.insert(
                header::CONTENT_TYPE,
                HeaderValue::from_static("application/xml"),
            );
            headers.insert("Depth", HeaderValue::from_static("0"));

            let request = self
                .get_http()?
                .request(propfind(), principal_url)
                .headers(headers)
                .body(S::homeset_body())
                .build()?;
            let response = self.send_request(request)?;
            let buf_reader = BufReader::new(response);
            let xml_reader = quick_xml::Reader::from_reader(buf_reader);
            let mut parser = parser::ListingParser::new(xml_reader);
            while let Some(response) = parser.next_response()? {
                if let Some(href) = S::get_homeset_url(&response) {
                    return Ok(base.join(&href)?);
                }
            }

            Err(DavError::NoHomesetUrl)?
        }
    }

    pub fn discover_impl<S: StorageType>(
        &mut self,
        config: DavConfig,
    ) -> Fallible<impl Iterator<Item = DavConfig>> {
        if config.collection.is_some() {
            Err(Error::BadDiscoveryConfig {
                msg: "collection argument must not be given when discovering collections/storages"
                    .to_owned(),
            })?;
        }

        let homeset_url = self.get_homeset_url::<S>()?;
        let mut headers = HeaderMap::new();
        headers.insert(
            header::CONTENT_TYPE,
            HeaderValue::from_static("application/xml"),
        );
        headers.insert("Depth", HeaderValue::from_static("1"));

        let request = self
            .get_http()?
            .request(propfind(), homeset_url)
            .headers(headers)
            .body(
                "<?xml version=\"1.0\" encoding=\"utf-8\" ?>\
                 <d:propfind xmlns:d=\"DAV:\">\
                 <d:prop>\
                 <d:resourcetype />\
                 </d:prop>\
                 </d:propfind>",
            )
            .build()?;
        let response = self.send_request(request)?;
        let buf_reader = BufReader::new(response);
        let xml_reader = quick_xml::Reader::from_reader(buf_reader);
        let mut parser = parser::ListingParser::new(xml_reader);

        let mut seen_urls = BTreeSet::new();
        let base = Url::parse(&config.url)?;

        Ok(parser
            .get_all_responses()?
            .into_iter()
            .filter_map(move |response| {
                if !S::is_valid_collection(&response) {
                    debug!("Skipping {:?}, not valid collection", response.href);
                    return None;
                }

                let collection_url = base.join(&response.href?).ok()?;
                let collection = S::collection_name_from_url(&collection_url)?;

                if seen_urls.contains(&collection_url) {
                    return None;
                }
                seen_urls.insert(collection_url.clone());

                Some(DavConfig {
                    url: collection_url.into_string(),
                    http: config.http.clone(),
                    collection: Some(collection),
                })
            }))
    }

    fn mkcol<S: StorageType>(&mut self, url: Url) -> Fallible<Url> {
        let xmltag = S::collection_resource_type();

        let request = self
            .get_http()?
            .request(mkcol(), url)
            .header(header::CONTENT_TYPE, "application/xml")
            .body(format!(
                r#"<?xml version="1.0" encoding="utf-8" ?>
                <d:mkcol xmlns:d="DAV:">
                    <d:set>
                        <d:prop>
                            <d:resourcetype>
                                <d:collection/>
                                {}
                            </d:resourcetype>
                        </d:prop>
                    </d:set>
                </d:mkcol>"#,
                xmltag
            ))
            .build()?;

        let response = self.send_request(request)?;
        Ok(response.url().clone())
    }

    fn prepare_create<S: StorageType>(&mut self, config: &DavConfig) -> Fallible<(String, Url)> {
        let url = Url::parse(&config.url)?;
        match config.collection {
            Some(ref x) => Ok((x.clone(), self.get_homeset_url::<S>()?.join(x)?)),
            None => match S::collection_name_from_url(&url) {
                Some(x) => Ok((x, url.clone())),
                None => Err(Error::BadDiscoveryConfig {
                    msg: "The URL is pointing to the root of the server, and `collection` is set to `null`. This means that vdirsyncer would attempt to create a collection at the root of the server. This is likely a misconfiguration. Set `collection` to an arbitrary name if you want auto-discovery.".to_owned()
                })?
            }
        }
    }

    fn get_meta<S: StorageType>(&mut self, key: Metadata) -> Fallible<String> {
        let xmltag = S::tagname_and_namespace_for_meta_key(key)?;

        let mut headers = HeaderMap::new();
        headers.insert(
            header::CONTENT_TYPE,
            HeaderValue::from_static("application/xml"),
        );
        headers.insert("Depth", HeaderValue::from_static("0"));

        let request = self
            .get_http()?
            .request(propfind(), &self.url)
            .headers(headers)
            .body(format!(
                r#"<?xml version="1.0" encoding="utf-8" ?>
                    <D:propfind xmlns:D="DAV:">
                        <D:prop>
                            {}
                        </D:prop>
                    </D:propfind>"#,
                xmltag
            ))
            .build()?;
        let response = self.send_request(request)?;
        let buf_reader = BufReader::new(response);
        let xml_reader = quick_xml::Reader::from_reader(buf_reader);
        let mut parser = parser::ListingParser::new(xml_reader);
        while let Some(response) = parser.next_response()? {
            match (key, response.displayname, response.apple_calendar_color) {
                (Metadata::Color, _, Some(value)) => {
                    return Ok(normalize_meta_value(&value).to_owned());
                }
                (Metadata::Displayname, Some(value), _) => {
                    return Ok(normalize_meta_value(&value).to_owned());
                }
                _ => (),
            }
        }

        Ok("".to_owned())
    }

    fn set_meta<S: StorageType>(&mut self, key: Metadata, value: &str) -> Fallible<()> {
        let xmltag = S::tagname_and_namespace_for_meta_key(key)?;

        let request = self
            .get_http()?
            .request(proppatch(), &self.url)
            .header(header::CONTENT_TYPE, "application/xml")
            .body(format!(
                r#"<?xml version="1.0" encoding="utf-8" ?>
                    <D:propertyupdate xmlns:D="DAV:">
                        <D:set>
                            <D:prop>
                                <{} xmlns="{}">{}</{}>
                            </D:prop>
                        </D:set>
                    </D:propertyupdate>"#,
                xmltag.0, xmltag.1, value, xmltag.0
            ))
            .build()?;

        let mut response = self.send_request(request)?;
        debug!("set_meta response: {:?}", response.text());

        // XXX: Response content is currently ignored. Though exceptions are
        // raised for HTTP errors, a multistatus with errorcodes inside is not
        // parsed yet. Not sure how common those are, or how they look like. It
        // might be easier (and safer in case of a stupid server) to just issue
        // a PROPFIND to see if the value got actually set.

        Ok(())
    }

    fn delete_collection(&mut self) -> Fallible<()> {
        let request = self
            .get_http()?
            .request(reqwest::Method::DELETE, &self.url)
            .build()?;

        let _ = self.send_request(request)?;
        Ok(())
    }
}

fn assert_multistatus_success(r: reqwest::Response) -> Fallible<reqwest::Response> {
    // TODO
    Ok(r)
}

#[derive(Clone, Serialize, Deserialize)]
pub struct DavConfig {
    url: String,

    #[serde(flatten)]
    http: HttpConfig,

    collection: Option<String>,
}

impl StorageConfig for DavConfig {
    fn get_collection(&self) -> Option<&str> {
        self.collection.as_ref().map(|x| &**x)
    }
}

pub mod exports {
    use super::super::http::init_http_config;
    use super::*;

    use chrono;

    #[derive(Debug, Fail, Shippai)]
    pub enum DavError {
        #[fail(display = "Server did not return etag.")]
        EtagNotFound,

        #[fail(display = "Server did not return a current-user-principal URL")]
        NoPrincipalUrl,

        #[fail(display = "Server did not return a home-set URL")]
        NoHomesetUrl,
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
        auth_cert_password: *const c_char,
    ) -> *mut Box<Storage> {
        let url = CStr::from_ptr(url);

        Box::into_raw(Box::new(Box::new(CarddavStorage::new(
            url.to_str().unwrap(),
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

    #[no_mangle]
    pub unsafe extern "C" fn vdirsyncer_init_caldav(
        url: *const c_char,
        username: *const c_char,
        password: *const c_char,
        useragent: *const c_char,
        verify_cert: *const c_char,
        auth_cert: *const c_char,
        auth_cert_password: *const c_char,
        start_date: i64,
        end_date: i64,
        include_vevent: bool,
        include_vjournal: bool,
        include_vtodo: bool,
    ) -> *mut Box<Storage> {
        let url = CStr::from_ptr(url);

        let parse_date = |i| {
            if i > 0 {
                Some(chrono::DateTime::from_utc(
                    chrono::NaiveDateTime::from_timestamp(i, 0),
                    chrono::Utc,
                ))
            } else {
                None
            }
        };

        let mut item_types = vec![];
        if include_vevent {
            item_types.push("VEVENT".to_owned());
        }
        if include_vjournal {
            item_types.push("VJOURNAL".to_owned());
        }
        if include_vtodo {
            item_types.push("VTODO".to_owned());
        }

        Box::into_raw(Box::new(Box::new(CaldavStorage::new(
            url.to_str().unwrap(),
            init_http_config(
                username,
                password,
                useragent,
                verify_cert,
                auth_cert,
                auth_cert_password,
            ),
            parse_date(start_date).and_then(|start| Some((start, parse_date(end_date)?))),
            item_types,
        ))))
    }
}

use exports::DavError;
