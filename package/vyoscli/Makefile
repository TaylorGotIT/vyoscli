#
# Copyright (C) 2026 vyoscli
#
# This is free software, licensed under the GNU General Public License v2.
#

include $(TOPDIR)/rules.mk

PKG_NAME:=vyoscli
PKG_VERSION:=0.1.0
PKG_RELEASE:=1

PKG_MAINTAINER:=you <you@example.com>
PKG_LICENSE:=GPL-2.0-or-later

PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)

include $(INCLUDE_DIR)/package.mk

define Package/vyoscli
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=VyOS-style CLI for OpenWrt
  URL:=https://github.com/yourname/vyoscli
  DEPENDS:=+python3 +python3-readline +ip-full +smartdns +adguardhome +frr +kmod-tcp-bbr +kmod-tcp-hybla +kmod-wireguard +wireguard-tools +openvpn-openssl +strongswan +conserver +podman +kmod-gre +kmod-ipip +kmod-vxlan
  PKGARCH:=all
endef

define Package/vyoscli/description
  A small VyOS-inspired command-line interface for OpenWrt.
  Features: operational / configuration modes, candidate config with
  commit/discard/save, Tab completion, and a declarative command tree.
endef

# Pure Python, no native build steps.
define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Configure
endef

define Build/Compile
endef

define Package/vyoscli/install
	$(INSTALL_DIR) $(1)/usr/lib/vyoscli
	$(INSTALL_DATA) ./files/usr/lib/vyoscli/__init__.py $(1)/usr/lib/vyoscli/
	$(INSTALL_DATA) ./files/usr/lib/vyoscli/__main__.py $(1)/usr/lib/vyoscli/
	$(INSTALL_DATA) ./files/usr/lib/vyoscli/cli.py $(1)/usr/lib/vyoscli/
	$(INSTALL_DATA) ./files/usr/lib/vyoscli/tree.py $(1)/usr/lib/vyoscli/
	$(INSTALL_DATA) ./files/usr/lib/vyoscli/config.py $(1)/usr/lib/vyoscli/
	$(INSTALL_DATA) ./files/usr/lib/vyoscli/commands.py $(1)/usr/lib/vyoscli/
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) ./files/usr/bin/vyoscli $(1)/usr/bin/vyoscli
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/etc/init.d/vyoscli $(1)/etc/init.d/vyoscli
	$(INSTALL_DIR) $(1)/etc/vyoscli
endef

define Package/vyoscli/postinst
#!/bin/sh
[ -n "$$IPKG_INSTROOT" ] || {
	/etc/init.d/vyoscli enable
}
exit 0
endef

$(eval $(call BuildPackage,vyoscli))