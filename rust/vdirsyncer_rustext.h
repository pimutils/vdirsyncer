#include <stdint.h>
#include <stdlib.h>
#include <stdbool.h>

typedef struct Box_Storage Box_Storage;

typedef struct Item Item;

typedef struct ShippaiError ShippaiError;

typedef struct VdirsyncerStorageListing VdirsyncerStorageListing;

typedef struct {
  Item *item;
  const char *etag;
} VdirsyncerStorageGetResult;

typedef struct {
  const char *href;
  const char *etag;
} VdirsyncerStorageUploadResult;

extern const uint8_t SHIPPAI_VARIANT_DavError_EtagNotFound;

extern const uint8_t SHIPPAI_VARIANT_Error_ItemAlreadyExisting;

extern const uint8_t SHIPPAI_VARIANT_Error_ItemNotFound;

extern const uint8_t SHIPPAI_VARIANT_Error_ItemUnparseable;

extern const uint8_t SHIPPAI_VARIANT_Error_MtimeMismatch;

extern const uint8_t SHIPPAI_VARIANT_Error_ReadOnly;

extern const uint8_t SHIPPAI_VARIANT_Error_UnexpectedVobject;

extern const uint8_t SHIPPAI_VARIANT_Error_UnexpectedVobjectVersion;

extern const uint8_t SHIPPAI_VARIANT_Error_UnsupportedVobject;

extern const uint8_t SHIPPAI_VARIANT_Error_WrongEtag;

void shippai_free_failure(ShippaiError *t);

void shippai_free_str(char *t);

const char *shippai_get_debug(ShippaiError *t);

const char *shippai_get_display(ShippaiError *t);

uint8_t shippai_get_variant_DavError(ShippaiError *t);

uint8_t shippai_get_variant_Error(ShippaiError *t);

bool shippai_is_error_DavError(ShippaiError *t);

bool shippai_is_error_Error(ShippaiError *t);

bool vdirsyncer_advance_storage_listing(VdirsyncerStorageListing *listing);

void vdirsyncer_free_item(Item *c);

void vdirsyncer_free_storage_get_result(VdirsyncerStorageGetResult *res);

void vdirsyncer_free_storage_listing(VdirsyncerStorageListing *listing);

void vdirsyncer_free_storage_upload_result(VdirsyncerStorageUploadResult *res);

void vdirsyncer_free_str(const char *s);

const char *vdirsyncer_get_hash(Item *c, ShippaiError **err);

const char *vdirsyncer_get_raw(Item *c);

const char *vdirsyncer_get_uid(Item *c);

Box_Storage *vdirsyncer_init_caldav(const char *url,
                                    const char *username,
                                    const char *password,
                                    const char *useragent,
                                    const char *verify_cert,
                                    const char *auth_cert,
                                    int64_t start_date,
                                    int64_t end_date,
                                    bool include_vevent,
                                    bool include_vjournal,
                                    bool include_vtodo);

Box_Storage *vdirsyncer_init_carddav(const char *url,
                                     const char *username,
                                     const char *password,
                                     const char *useragent,
                                     const char *verify_cert,
                                     const char *auth_cert);

Box_Storage *vdirsyncer_init_filesystem(const char *path,
                                        const char *fileext,
                                        const char *post_hook);

Box_Storage *vdirsyncer_init_http(const char *url,
                                  const char *username,
                                  const char *password,
                                  const char *useragent,
                                  const char *verify_cert,
                                  const char *auth_cert);

void vdirsyncer_init_logger(void);

Box_Storage *vdirsyncer_init_singlefile(const char *path);

Item *vdirsyncer_item_from_raw(const char *s);

bool vdirsyncer_item_is_parseable(Item *c);

void vdirsyncer_storage_buffered(Box_Storage *storage);

void vdirsyncer_storage_delete(Box_Storage *storage,
                               const char *c_href,
                               const char *c_etag,
                               ShippaiError **err);

void vdirsyncer_storage_flush(Box_Storage *storage, ShippaiError **err);

void vdirsyncer_storage_free(Box_Storage *storage);

VdirsyncerStorageGetResult *vdirsyncer_storage_get(Box_Storage *storage,
                                                   const char *c_href,
                                                   ShippaiError **err);

VdirsyncerStorageListing *vdirsyncer_storage_list(Box_Storage *storage, ShippaiError **err);

const char *vdirsyncer_storage_listing_get_etag(VdirsyncerStorageListing *listing);

const char *vdirsyncer_storage_listing_get_href(VdirsyncerStorageListing *listing);

const char *vdirsyncer_storage_update(Box_Storage *storage,
                                      const char *c_href,
                                      Item *item,
                                      const char *c_etag,
                                      ShippaiError **err);

VdirsyncerStorageUploadResult *vdirsyncer_storage_upload(Box_Storage *storage,
                                                         Item *item,
                                                         ShippaiError **err);

Item *vdirsyncer_with_uid(Item *c, const char *uid, ShippaiError **err);
