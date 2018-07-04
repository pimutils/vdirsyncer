use super::{parser, DavClient, DavConfig, StorageType, XmlTag};

use storage::http::HttpConfig;
use storage::utils::generate_href;
use storage::{ConfigurableStorage, Metadata, Storage, StorageConfig};

use errors::*;
use item::Item;

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

        config.url = dav.mkcol::<CarddavType>(collection_url)?.into_string();
        Ok(config)
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
