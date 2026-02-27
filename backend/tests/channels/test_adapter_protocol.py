"""
Tests for the ChannelAdapter Protocol class.

Verifies that:
1. A conforming class satisfies isinstance() check
2. A non-conforming class (no send method) fails isinstance() check
3. The Protocol is importable from the channels package
4. The Protocol is runtime_checkable (isinstance does not raise TypeError)
"""
from channels.adapter import ChannelAdapter
from channels.models import InternalMessage


class _ConformingAdapter:
    """A class that implements the ChannelAdapter protocol."""

    async def send(self, msg: InternalMessage) -> None:
        pass


class _NoSendAdapter:
    """A class that does NOT implement the ChannelAdapter protocol."""

    async def receive(self, msg: InternalMessage) -> None:
        pass


def test_conforming_adapter_satisfies_protocol() -> None:
    """A class with async def send(msg: InternalMessage) -> None passes isinstance()."""
    adapter = _ConformingAdapter()
    assert isinstance(adapter, ChannelAdapter)


def test_non_conforming_class_fails_protocol() -> None:
    """A class without a send method fails isinstance()."""
    bad = _NoSendAdapter()
    assert not isinstance(bad, ChannelAdapter)


def test_import_from_package() -> None:
    """ChannelAdapter is exported from channels.__init__.py."""
    from channels import ChannelAdapter as PackageExport

    assert PackageExport is ChannelAdapter


def test_protocol_is_runtime_checkable() -> None:
    """The Protocol has __protocol_attrs__ confirming @runtime_checkable is applied."""
    # runtime_checkable protocols have _is_runtime_protocol set to True
    assert getattr(ChannelAdapter, "_is_runtime_protocol", False) is True
    # isinstance() does not raise TypeError (would if not runtime_checkable)
    result = isinstance(object(), ChannelAdapter)
    assert result is False
