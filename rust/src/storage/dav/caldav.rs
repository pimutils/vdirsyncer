use chrono;

use reqwest::header;

use super::dav_methods::*;
use super::parser;
use super::{DavClient, DavConfig, StorageType, XmlTag};
use storage::http::HttpConfig;
use storage::utils::generate_href;
use storage::{ConfigurableStorage, Metadata, Storage, StorageConfig};

use errors::*;
use item::Item;

static CALDAV_DT_FORMAT: &'static str = "%Y%m%dT%H%M%SZ";

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
            }).collect()
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
            let mut headers = header::HeaderMap::new();
            headers.insert(
                header::CONTENT_TYPE,
                header::HeaderValue::from_static("application/xml"),
            );
            headers.insert("Depth", header::HeaderValue::from_static("1"));

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

        Ok(Box::new(dav.discover_impl::<CaldavType>(config.dav)?.map(
            move |dav| CaldavConfig {
                start_date: start_date.clone(),
                end_date: end_date.clone(),
                item_types: item_types.clone(),
                dav,
            },
        )))
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

        config.dav.url = dav.mkcol::<CaldavType>(collection_url)?.into_string();
        Ok(config)
    }
}

enum CaldavType {}

impl StorageType for CaldavType {
    fn tagname_and_namespace_for_meta_key(key: Metadata) -> Fallible<XmlTag> {
        match key {
            Metadata::Displayname => Ok(XmlTag("displayname", "DAV:")),
            Metadata::Color => Ok(XmlTag("calendar-color", "http://apple.com/ns/ical/")),
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
