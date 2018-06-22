mod dav;
pub mod exports;
mod filesystem;
mod http;
mod singlefile;
mod utils;
use errors::Fallible;
use item::Item;
use serde::{Deserialize, Serialize};

type ItemAndEtag = (Item, String);

pub trait StorageConfig: Clone + Serialize + Deserialize<'static> {
    /// Get the collection key of the object, if any.
    fn get_collection(&self) -> Option<&str>;
}

pub trait ConfigurableStorage: Storage + Sized {
    /// An instance of a configuration can be used to configure a storage and/or to discover
    /// storages.
    ///
    /// If a user configures a storage, the entire map in the configuration file is serialized into
    /// an instance of this type.
    type Config: StorageConfig;

    /// Load storage from configuration
    fn from_config(config: Self::Config) -> Fallible<Self>;

    /// Discover collections. Take a configuration like the user specified and yield configurations
    /// that actually point to valid storages.
    fn discover(config: Self::Config) -> Fallible<Box<Iterator<Item = Self::Config>>>;

    /// Create a new collection, honoring the `collection` value:
    ///
    /// * `collection == Some(_)` means that the storage should use the given name for the
    ///   collection. If it fails to do so, the `collection` in the return value may be different.
    /// * `collection = None` means that the configuration already points to a new storage
    ///   location. In that case the configuration can usually be returned as-is, but does not have
    ///   to be.
    ///
    /// The return value should have a non-`None` collection value.
    fn create(config: Self::Config) -> Fallible<Self::Config>;
}

pub trait Storage {
    /// returns an iterator of `(href, etag)`
    fn list<'a>(&'a mut self) -> Fallible<Box<Iterator<Item = (String, String)> + 'a>>;

    ///Fetch a single item.
    ///
    ///:param href: href to fetch
    ///:returns: (item, etag)
    ///:raises: :exc:`vdirsyncer.exceptions.PreconditionFailed` if item can't be found.
    fn get(&mut self, href: &str) -> Fallible<ItemAndEtag>;

    /// Upload a new item.
    ///
    /// In cases where the new etag cannot be atomically determined (i.e. in the same
    /// "transaction" as the upload itself), this method may return `None` as etag. This
    /// special case only exists because of DAV. Avoid this situation whenever possible.
    ///
    /// Returns `(href, etag)`
    fn upload(&mut self, item: Item) -> Fallible<(String, String)>;

    /// Update an item.
    ///
    /// The etag may be none in some cases, see `upload`.
    ///
    /// Returns `etag`
    fn update(&mut self, href: &str, item: Item, etag: &str) -> Fallible<String>;

    /// Delete an item by href.
    fn delete(&mut self, href: &str, etag: &str) -> Fallible<()>;

    /// Enter buffered mode for storages that support it.
    ///
    /// Uploads, updates and deletions may not be effective until `flush` is explicitly called.
    ///
    /// Use this if you will potentially write a lot of data to the storage, it improves
    /// performance for storages that implement it.
    fn buffered(&mut self) {}

    /// Write back all changes to the collection.
    fn flush(&mut self) -> Fallible<()> {
        Ok(())
    }
}
