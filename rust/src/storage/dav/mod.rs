mod parser;

use chrono;

use std::fmt;
use std::collections::BTreeSet;
use std::io::{BufReader, Read};
use std::str::FromStr;

use quick_xml;
use reqwest;
use reqwest::header::{ContentType, ETag, EntityTag, IfMatch, IfNoneMatch};
use url::Url;

use super::http::{handle_http_error, send_request, HttpConfig};
use super::utils::generate_href;
use super::{normalize_meta_value, ConfigurableStorage, Metadata, Storage, StorageConfig};
use errors::*;

use item::Item;

#[derive(Debug, Clone, Copy)]
struct XmlTag(&'static str, &'static str); // tagname, namespace

impl fmt::Display for XmlTag {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "<{} xmlns=\"{}\"/>", self.0, self.1)
    }
}

#[inline]
fn propfind() -> reqwest::Method {
    reqwest::Method::Extension("PROPFIND".to_owned())
}

#[inline]
fn proppatch() -> reqwest::Method {
    reqwest::Method::Extension("PROPPATCH".to_owned())
}

#[inline]
fn report() -> reqwest::Method {
    reqwest::Method::Extension("REPORT".to_owned())
}

#[inline]
fn mkcol() -> reqwest::Method {
    reqwest::Method::Extension("MKCOL".to_owned())
}

trait StorageType {
    fn tagname_and_namespace_for_meta_key(key: Metadata) -> Fallible<XmlTag>;

    fn well_known_path() -> &'static str;

    fn homeset_body() -> &'static str;

    fn get_homeset_url(response: &parser::Response) -> Option<&str>;

    fn is_valid_collection(response: &parser::Response) -> bool;

    fn collection_resource_type() -> XmlTag;
}

enum CaldavType {}

impl StorageType for CaldavType {
    fn tagname_and_namespace_for_meta_key(key: Metadata) -> Fallible<XmlTag> {
        match key {
            Metadata::Displayname => Ok(XmlTag("displayname", "DAV:")),
            Metadata::Color => Ok(XmlTag("calendar-color", "http://apple.com/ns/ical/"))
        }
    }

    fn well_known_path() -> &'static str {
        "/.well-known/caldav"
    }

    fn homeset_body() -> &'static str {
                    "<d:propfind xmlns:d=\"DAV:\" xmlns:c=\"urn:ietf:params:xml:ns:caldav\">\
                     <d:prop>\
                     <c:calendar-home-set />\
                     </d:prop>\
                     </d:propfind>"
    }

    fn get_homeset_url(response: &parser::Response) -> Option<&str> {
        response.calendar_home_set.as_ref().map(|x| &**x)
    }

    fn is_valid_collection(response: &parser::Response) -> bool {
        response.is_calendar
    }

    fn collection_resource_type() -> XmlTag {
        XmlTag("calendar", "urn:ietf:params:xml:ns:caldav")
    }
}


enum CarddavType {}

impl StorageType for CarddavType {
    fn tagname_and_namespace_for_meta_key(key: Metadata) -> Fallible<XmlTag> {
        match key {
            Metadata::Displayname => Ok(XmlTag("displayname", "DAV:")),
            Metadata::Color => Err(Error::MetadataValueUnsupported {
                msg: "Colors are only supported on calendars (not a vdirsyncer limitation).",
            })?,
        }
    }

    fn well_known_path() -> &'static str {
        "/.well-known/carddav"
    }

    fn homeset_body() -> &'static str {

                    "<d:propfind xmlns:d=\"DAV:\" xmlns:c=\"urn:ietf:params:xml:ns:carddav\">\
                     <d:prop>\
                     <c:addressbook-home-set />\
                     </d:prop>\
                     </d:propfind>"
    }

    fn get_homeset_url(response: &parser::Response) -> Option<&str> {
        response.addressbook_home_set.as_ref().map(|x| &**x)
    }

    fn is_valid_collection(response: &parser::Response) -> bool {
        response.is_addressbook
    }

    fn collection_resource_type() -> XmlTag {
        XmlTag("addressbook", "urn:ietf:params:xml:ns:carddav")
    }
}

static CALDAV_DT_FORMAT: &'static str = "%Y%m%dT%H%M%SZ";

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
        let etag = match response.headers().get::<ETag>() {
            Some(x) => format!("\"{}\"", x.tag()),
            None => Err(DavError::EtagNotFound)?,
        };
        Ok((Item::from_raw(s), etag))
    }

    pub fn list<'a>(
        &'a mut self,
        mimetype_contains: &'a str,
    ) -> Fallible<Box<Iterator<Item = (String, String)> + 'a>> {
        let mut headers = reqwest::header::Headers::new();
        headers.set(ContentType::xml());
        headers.set_raw("Depth", "1");

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
        let mut request = self.get_http()?.request(reqwest::Method::Put, url);
        request.header(ContentType(reqwest::mime::Mime::from_str(mimetype)?));
        if let Some(etag) = etag {
            request.header(IfMatch::Items(vec![EntityTag::new(
                false,
                etag.trim_matches('"').to_owned(),
            )]));
        } else {
            request.header(IfNoneMatch::Any);
        }

        let raw = item.get_raw();
        let response = send_request(&self.get_http()?, request.body(raw).build()?)?;

        match (etag, response.status()) {
            (Some(_), reqwest::StatusCode::PreconditionFailed) => Err(Error::WrongEtag {
                href: href.to_owned(),
            })?,
            (None, reqwest::StatusCode::PreconditionFailed) => Err(Error::ItemAlreadyExisting {
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
        let etag = match response.headers().get::<ETag>() {
            Some(x) => format!("\"{}\"", x.tag()),
            None => "".to_owned(),
        };
        Ok((response.url().path().to_owned(), etag))
    }

    fn delete(&mut self, href: &str, etag: &str) -> Fallible<()> {
        let base = Url::parse(&self.url)?;
        let url = base.join(href)?;
        let request = self
            .get_http()?
            .request(reqwest::Method::Delete, url)
            .header(IfMatch::Items(vec![EntityTag::new(
                false,
                etag.trim_matches('"').to_owned(),
            )]))
            .build()?;
        let response = send_request(&self.get_http()?, request)?;

        if response.status() == reqwest::StatusCode::PreconditionFailed {
            Err(Error::WrongEtag {
                href: href.to_owned(),
            })?;
        }

        assert_multistatus_success(handle_http_error(href, response)?)?;
        Ok(())
    }

    fn get_well_known_url<S: StorageType>(&mut self) -> Fallible<Url> {
        let url = Url::parse(&self.url)?;
        let request = self.get_http()?.get(url.join(S::well_known_path())?).build()?;
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

        let mut headers = reqwest::header::Headers::new();
        headers.set(ContentType::xml());
        headers.set_raw("Depth", "0");

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

            let mut headers = reqwest::header::Headers::new();
            headers.set(ContentType::xml());
            headers.set_raw("Depth", "0");

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
        let mut headers = reqwest::header::Headers::new();
        headers.set(ContentType::xml());
        headers.set_raw("Depth", "1");

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
                let collection = collection_name_from_url(&collection_url)?;

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
            .header(ContentType::xml())
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

    fn prepare_create<S: StorageType>(
        &mut self,
        config: &DavConfig,
    ) -> Fallible<(String, Url)> {
        let url = Url::parse(&config.url)?;
        match config.collection {
            Some(ref x) => Ok((x.clone(), self.get_homeset_url::<S>()?.join(x)?)),
            None => match collection_name_from_url(&url) {
                Some(x) => Ok((x, url.clone())),
                None => Err(Error::BadDiscoveryConfig {
                    msg: "The URL is pointing to the root of the server, and `collection` is set to `null`. This means that vdirsyncer would attempt to create a collection at the root of the server. This is likely a misconfiguration. Set `collection` to an arbitrary name if you want auto-discovery.".to_owned()
                })?
            }
        }
    }

    fn get_meta<S: StorageType>(&mut self, key: Metadata) -> Fallible<String> {
        let xmltag = S::tagname_and_namespace_for_meta_key(key)?;

        let mut headers = reqwest::header::Headers::new();
        headers.set(ContentType::xml());
        headers.set_raw("Depth", "0");

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
                    return Ok(normalize_meta_value(&value).to_owned())
                }
                (Metadata::Displayname, Some(value), _) => {
                    return Ok(normalize_meta_value(&value).to_owned())
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
            .header(ContentType::xml())
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
            .request(reqwest::Method::Delete, &self.url)
            .build()?;

        let _ = self.send_request(request)?;
        Ok(())
    }
}

fn assert_multistatus_success(r: reqwest::Response) -> Fallible<reqwest::Response> {
    // TODO
    Ok(r)
}

pub struct CarddavStorage {
    inner: DavClient,
}

impl CarddavStorage {
    pub fn new(url: &str, http_config: HttpConfig) -> Self {
        CarddavStorage {
            inner: DavClient::new(url, http_config),
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

    fn upload(&mut self, item: Item) -> Fallible<(String, String)> {
        let href = format!("{}.vcf", generate_href(&item.get_ident()?));
        self.inner.put(&href, &item, "text/vcard", None)
    }

    fn update(&mut self, href: &str, item: Item, etag: &str) -> Fallible<String> {
        self.inner
            .put(&href, &item, "text/vcard", Some(etag))
            .map(|x| x.1)
    }

    fn delete(&mut self, href: &str, etag: &str) -> Fallible<()> {
        self.inner.delete(href, etag)
    }

    fn get_meta(&mut self, key: Metadata) -> Fallible<String> {
        self.inner.get_meta::<CarddavType>(key)
    }

    fn set_meta(&mut self, key: Metadata, value: &str) -> Fallible<()> {
        self.inner.set_meta::<CarddavType>(key, value)
    }

    fn delete_collection(&mut self) -> Fallible<()> {
        self.inner.delete_collection()
    }
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

impl ConfigurableStorage for CarddavStorage {
    type Config = DavConfig;

    fn from_config(config: Self::Config) -> Fallible<Self> {
        Ok(CarddavStorage::new(&config.url, config.http))
    }

    fn discover(config: Self::Config) -> Fallible<Box<Iterator<Item = Self::Config>>> {
        let mut dav = DavClient::new(&config.url, config.http.clone());
        Ok(Box::new(dav.discover_impl::<CarddavType>(config)?))
    }

    fn create(mut config: Self::Config) -> Fallible<Self::Config> {
        let mut dav = DavClient::new(&config.url, config.http.clone());

        let (collection, collection_url) = dav.prepare_create::<CarddavType>(&config)?;

        if let Ok(discover_iter) = Self::discover(config.clone()) {
            for discover_res in discover_iter {
                if discover_res.get_collection() == Some(&collection) {
                    return Ok(discover_res);
                }
            }
        }

        config.url = dav
            .mkcol::<CarddavType>(collection_url)?
            .into_string();
        Ok(config)
    }
}

pub struct CaldavStorage {
    inner: DavClient,
    date_range: Option<(chrono::DateTime<chrono::Utc>, chrono::DateTime<chrono::Utc>)>,
    item_types: Vec<String>,
}

impl CaldavStorage {
    pub fn new(
        url: &str,
        http_config: HttpConfig,
        date_range: Option<(chrono::DateTime<chrono::Utc>, chrono::DateTime<chrono::Utc>)>,
        item_types: Vec<String>,
    ) -> Self {
        CaldavStorage {
            inner: DavClient::new(url, http_config),
            date_range,
            item_types,
        }
    }

    #[inline]
    fn get_caldav_filters(&self) -> Vec<String> {
        let mut item_types = self.item_types.clone();
        let mut timefilter = "".to_owned();

        if let Some((start, end)) = self.date_range {
            timefilter = format!(
                "<C:time-range start=\"{}\" end=\"{}\" />",
                start.format(CALDAV_DT_FORMAT),
                end.format(CALDAV_DT_FORMAT)
            );

            if item_types.is_empty() {
                item_types.push("VTODO".to_owned());
                item_types.push("VEVENT".to_owned());
            }
        }

        item_types
            .into_iter()
            .map(|item_type| {
                format!(
                    "<C:comp-filter name=\"VCALENDAR\">
                     <C:comp-filter name=\"{}\">{}</C:comp-filter>\
                     </C:comp-filter>",
                    item_type, timefilter
                )
            })
            .collect()
    }
}

impl Storage for CaldavStorage {
    fn list<'a>(&'a mut self) -> Fallible<Box<Iterator<Item = (String, String)> + 'a>> {
        let filters = self.get_caldav_filters();
        if filters.is_empty() {
            // If we don't have any filters (which is the default), taking the
            // risk of sending a calendar-query is not necessary. There doesn't
            // seem to be a widely-usable way to send calendar-queries with the
            // same semantics as a PROPFIND request... so why not use PROPFIND
            // instead?
            //
            // See https://github.com/dmfs/tasks/issues/118 for backstory.
            self.inner.list("text/calendar")
        } else {
            let mut rv = vec![];
            let mut headers = reqwest::header::Headers::new();
            headers.set(ContentType::xml());
            headers.set_raw("Depth", "1");

            for filter in filters {
                let data =
                    format!(
                    "<?xml version=\"1.0\" encoding=\"utf-8\" ?>\
                     <C:calendar-query xmlns:D=\"DAV:\" xmlns:C=\"urn:ietf:params:xml:ns:caldav\">\
                     <D:prop><D:getcontenttype/><D:getetag/></D:prop>\
                     <C:filter>{}</C:filter>\
                     </C:calendar-query>", filter);

                let request = self
                    .inner
                    .get_http()?
                    .request(report(), &self.inner.url)
                    .headers(headers.clone())
                    .body(data)
                    .build()?;
                let response = self.inner.send_request(request)?;
                rv.extend(
                    self.inner
                        .parse_item_listing_response(response, "text/calendar")?,
                );
            }

            Ok(Box::new(rv.into_iter()))
        }
    }

    fn get(&mut self, href: &str) -> Fallible<(Item, String)> {
        self.inner.get(href)
    }

    fn upload(&mut self, item: Item) -> Fallible<(String, String)> {
        let href = format!("{}.ics", generate_href(&item.get_ident()?));
        self.inner.put(&href, &item, "text/calendar", None)
    }

    fn update(&mut self, href: &str, item: Item, etag: &str) -> Fallible<String> {
        self.inner
            .put(href, &item, "text/calendar", Some(etag))
            .map(|x| x.1)
    }

    fn delete(&mut self, href: &str, etag: &str) -> Fallible<()> {
        self.inner.delete(href, etag)
    }

    fn get_meta(&mut self, key: Metadata) -> Fallible<String> {
        self.inner.get_meta::<CaldavType>(key)
    }

    fn set_meta(&mut self, key: Metadata, value: &str) -> Fallible<()> {
        self.inner.set_meta::<CaldavType>(key, value)
    }

    fn delete_collection(&mut self) -> Fallible<()> {
        self.inner.delete_collection()
    }
}

#[derive(Clone, Serialize, Deserialize)]
pub struct CaldavConfig {
    item_types: Option<Vec<String>>,
    start_date: Option<String>,
    end_date: Option<String>,
    #[serde(flatten)]
    dav: DavConfig,
}

impl StorageConfig for CaldavConfig {
    fn get_collection(&self) -> Option<&str> {
        self.dav.get_collection()
    }
}

impl ConfigurableStorage for CaldavStorage {
    type Config = CaldavConfig;

    fn from_config(_config: Self::Config) -> Fallible<Self> {
        unimplemented!();
    }

    fn discover(config: Self::Config) -> Fallible<Box<Iterator<Item = Self::Config>>> {
        let mut dav = DavClient::new(&config.dav.url, config.dav.http.clone());

        let item_types = config.item_types;
        let start_date = config.start_date;
        let end_date = config.end_date;

        Ok(Box::new(
            dav.discover_impl::<CaldavType>(config.dav)?
                .map(move |dav| CaldavConfig {
                    start_date: start_date.clone(),
                    end_date: end_date.clone(),
                    item_types: item_types.clone(),
                    dav,
                }),
        ))
    }

    fn create(mut config: Self::Config) -> Fallible<Self::Config> {
        let mut dav = DavClient::new(&config.dav.url, config.dav.http.clone());

        let (collection, collection_url) = dav.prepare_create::<CaldavType>(&config.dav)?;

        if let Ok(discover_iter) = Self::discover(config.clone()) {
            for discover_res in discover_iter {
                if discover_res.get_collection() == Some(&collection) {
                    return Ok(discover_res);
                }
            }
        }

        config.dav.url = dav
            .mkcol::<CaldavType>(collection_url)?
            .into_string();
        Ok(config)
    }
}

pub mod exports {
    use super::super::http::init_http_config;
    use super::*;

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

fn collection_name_from_url(url: &Url) -> Option<String> {
    Some(
        url.path_segments()?
            .rev()
            .find(|x| !x.is_empty())?
            .to_owned(),
    )
}
