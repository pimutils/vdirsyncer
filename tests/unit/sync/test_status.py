import hypothesis.strategies as st
from hypothesis import assume
from hypothesis import given

from vdirsyncer.sync.status import SqliteStatus


status_dict_strategy = st.dictionaries(
    st.text(),
    st.tuples(
        *(
            st.fixed_dictionaries(
                {"href": st.text(), "hash": st.text(), "etag": st.text()}
            )
            for _ in range(2)
        )
    ),
)


@given(status_dict=status_dict_strategy)
def test_legacy_status(status_dict):
    hrefs_a = {meta_a["href"] for meta_a, meta_b in status_dict.values()}
    hrefs_b = {meta_b["href"] for meta_a, meta_b in status_dict.values()}
    assume(len(hrefs_a) == len(status_dict) == len(hrefs_b))
    status = SqliteStatus()
    status.load_legacy_status(status_dict)
    assert dict(status.to_legacy_status()) == status_dict

    for ident, (meta_a, meta_b) in status_dict.items():
        ident_a, meta2_a = status.get_by_href_a(meta_a["href"])
        ident_b, meta2_b = status.get_by_href_b(meta_b["href"])
        assert meta2_a.to_status() == meta_a
        assert meta2_b.to_status() == meta_b
        assert ident_a == ident_b == ident
