#!/usr/bin/env python

'''
Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''

import datetime
import glob
import os
import re
import shutil
import stat
import string
import sys
import tempfile

from ambari_commons.exceptions import FatalException
from ambari_commons.os_check import OSCheck, OSConst
from ambari_commons.os_family_impl import OsFamilyImpl
from ambari_commons.os_utils import run_os_command, search_file, set_file_permissions
from ambari_commons.logging_utils import get_debug_mode, print_info_msg, print_warning_msg, print_error_msg, \
  set_debug_mode
from ambari_server.properties import Properties
from ambari_server.userInput import get_validated_string_input
from ambari_server.utils import compare_versions, locate_file


OS_VERSION = OSCheck().get_os_major_version()
OS_TYPE = OSCheck.get_os_type()
OS_FAMILY = OSCheck.get_os_family()

PID_NAME = "ambari-server.pid"

# Non-root user setup commands
NR_USER_PROPERTY = "ambari-server.user"

BLIND_PASSWORD = "*****"

# Common messages
PRESS_ENTER_MSG = "Press <enter> to continue."

OS_FAMILY_PROPERTY = "server.os_family"
OS_TYPE_PROPERTY = "server.os_type"

BOOTSTRAP_DIR_PROPERTY = "bootstrap.dir"

AMBARI_CONF_VAR = "AMBARI_CONF_DIR"
AMBARI_PROPERTIES_FILE = "ambari.properties"
AMBARI_ENV_FILE = "ambari-env.sh"
AMBARI_KRB_JAAS_LOGIN_FILE = "krb5JAASLogin.conf"
GET_FQDN_SERVICE_URL = "server.fqdn.service.url"

SERVER_OUT_FILE_KEY = "ambari.output.file.path"
VERBOSE_OUTPUT_KEY = "ambari.output.verbose"

DEBUG_MODE_KEY = "ambari.server.debug"
SUSPEND_START_MODE_KEY = "ambari.server.debug.suspend.start"

# Environment variables
AMBARI_SERVER_LIB = "AMBARI_SERVER_LIB"
JAVA_HOME = "JAVA_HOME"

AMBARI_VERSION_VAR = "AMBARI_VERSION_VAR"

# JDK
JAVA_HOME_PROPERTY = "java.home"
JDK_NAME_PROPERTY = "jdk.name"
JCE_NAME_PROPERTY = "jce.name"
JDK_DOWNLOAD_SUPPORTED_PROPERTY = "jdk.download.supported"
JCE_DOWNLOAD_SUPPORTED_PROPERTY = "jce.download.supported"

# JDBC
JDBC_PATTERNS = {"oracle": "*ojdbc*.jar", "mysql": "*mysql*.jar", "mssql": "*sqljdbc*.jar"}

#TODO property used incorrectly in local case, it was meant to be dbms name, not postgres database name,
# has workaround for now, as we don't need dbms name if persistence_type=local
JDBC_DATABASE_PROPERTY = "server.jdbc.database"                 # E.g., embedded|oracle|mysql|mssql|postgres
JDBC_DATABASE_NAME_PROPERTY = "server.jdbc.database_name"       # E.g., ambari. Not used on Windows.
JDBC_HOSTNAME_PROPERTY = "server.jdbc.hostname"
JDBC_PORT_PROPERTY = "server.jdbc.port"
JDBC_POSTGRES_SCHEMA_PROPERTY = "server.jdbc.postgres.schema"   # Only for postgres, defaults to same value as DB name
JDBC_SQLA_SERVER_NAME = "server.jdbc.sqla.server_name"

JDBC_USER_NAME_PROPERTY = "server.jdbc.user.name"
JDBC_PASSWORD_PROPERTY = "server.jdbc.user.passwd"
JDBC_PASSWORD_FILENAME = "password.dat"
JDBC_RCA_PASSWORD_FILENAME = "rca_password.dat"

CLIENT_API_PORT_PROPERTY = "client.api.port"
CLIENT_API_PORT = "8080"

SERVER_VERSION_FILE_PATH = "server.version.file"

PERSISTENCE_TYPE_PROPERTY = "server.persistence.type"
JDBC_DRIVER_PROPERTY = "server.jdbc.driver"
JDBC_DRIVER_PATH_PROPERTY = "server.jdbc.driver.path"
JDBC_URL_PROPERTY = "server.jdbc.url"

JDBC_RCA_DATABASE_PROPERTY = "server.jdbc.database"
JDBC_RCA_HOSTNAME_PROPERTY = "server.jdbc.hostname"
JDBC_RCA_PORT_PROPERTY = "server.jdbc.port"
JDBC_RCA_SCHEMA_PROPERTY = "server.jdbc.schema"

JDBC_RCA_DRIVER_PROPERTY = "server.jdbc.rca.driver"
JDBC_RCA_URL_PROPERTY = "server.jdbc.rca.url"
JDBC_RCA_USER_NAME_PROPERTY = "server.jdbc.rca.user.name"
JDBC_RCA_PASSWORD_FILE_PROPERTY = "server.jdbc.rca.user.passwd"

DEFAULT_DBMS_PROPERTY = "server.setup.default.dbms"

JDBC_RCA_PASSWORD_ALIAS = "ambari.db.password"

### # Windows-specific # ###

JDBC_USE_INTEGRATED_AUTH_PROPERTY = "server.jdbc.use.integrated.auth"

JDBC_RCA_USE_INTEGRATED_AUTH_PROPERTY = "server.jdbc.rca.use.integrated.auth"

### # End Windows-specific # ###

# resources repo configuration
RESOURCES_DIR_PROPERTY = "resources.dir"

# stack repo upgrade
STACK_LOCATION_KEY = 'metadata.path'

# LDAP security
IS_LDAP_CONFIGURED = "ambari.ldap.isConfigured"
LDAP_MGR_PASSWORD_ALIAS = "ambari.ldap.manager.password"
LDAP_MGR_PASSWORD_PROPERTY = "authentication.ldap.managerPassword"
LDAP_MGR_PASSWORD_FILENAME = "ldap-password.dat"
LDAP_MGR_USERNAME_PROPERTY = "authentication.ldap.managerDn"
LDAP_PRIMARY_URL_PROPERTY = "authentication.ldap.primaryUrl"

# SSL truststore
SSL_TRUSTSTORE_PASSWORD_ALIAS = "ambari.ssl.trustStore.password"
SSL_TRUSTSTORE_PATH_PROPERTY = "ssl.trustStore.path"
SSL_TRUSTSTORE_PASSWORD_PROPERTY = "ssl.trustStore.password"
SSL_TRUSTSTORE_TYPE_PROPERTY = "ssl.trustStore.type"

# SSL common
SSL_API = 'api.ssl'
SSL_API_PORT = 'client.api.ssl.port'
DEFAULT_SSL_API_PORT = 8443

# JDK
JDK_RELEASES="java.releases"

VIEWS_DIR_PROPERTY = "views.dir"

#Common setup or upgrade message
SETUP_OR_UPGRADE_MSG = "- If this is a new setup, then run the \"ambari-server setup\" command to create the user\n" \
                       "- If this is an upgrade of an existing setup, run the \"ambari-server upgrade\" command.\n" \
                       "Refer to the Ambari documentation for more information on setup and upgrade."

DEFAULT_DB_NAME = "ambari"

class ServerDatabaseType(object):
  internal = 0
  remote = 1


class ServerDatabaseEntry(object):
  def __init__(self, name, title, db_type, aliases=None):
    """
    :type name str
    :type title str
    :type db_type int
    :type aliases list
    """
    self.__name = name
    self.__title = title
    self.__type = db_type
    if aliases is None:
      aliases = []

    self.__aliases = aliases

  @property
  def name(self):
    return self.__name

  @property
  def title(self):
    return self.__title

  @property
  def dbtype(self):
    return self.__type

  def __str__(self):
    return self.name

  def __eq__(self, other):
    if other is None:
      return False

    if isinstance(other, ServerDatabaseEntry):
      return self.name == other.name and self.dbtype == other.dbtype
    elif isinstance(other, str):
      return self.name == other or other in self.__aliases

    raise RuntimeError("Not compatible type")


class ServerDatabases(object):
  postgres = ServerDatabaseEntry("postgres", "Postgres", ServerDatabaseType.remote)
  oracle = ServerDatabaseEntry("oracle", "Oracle", ServerDatabaseType.remote)
  mysql = ServerDatabaseEntry("mysql", "MySQL", ServerDatabaseType.remote)
  mssql = ServerDatabaseEntry("mssql", "MSSQL", ServerDatabaseType.remote)
  derby = ServerDatabaseEntry("derby", "Derby", ServerDatabaseType.remote)
  sqlanywhere = ServerDatabaseEntry("sqlanywhere", "SQL Anywhere", ServerDatabaseType.remote)
  postgres_internal = ServerDatabaseEntry("postgres", "Embedded Postgres", ServerDatabaseType.internal, aliases=['embedded'])

  @staticmethod
  def databases():
    props = ServerDatabases.__dict__
    r_props = []
    for p in props:
      if isinstance(props[p], ServerDatabaseEntry):
        r_props.append(props[p].name)

    return set(r_props)

  @staticmethod
  def match(name):
    """
    :type name str
    :rtype ServerDatabaseEntry
    """
    props = ServerDatabases.__dict__

    for p in props:
      if isinstance(props[p], ServerDatabaseEntry):
        if name == props[p]:
          return props[p]

    return None

class ServerConfigDefaults(object):
  def __init__(self):
    self.JAVA_SHARE_PATH = "/usr/share/java"
    self.SHARE_PATH = "/usr/share"
    self.OUT_DIR = os.sep + os.path.join("var", "log", "ambari-server")
    self.SERVER_OUT_FILE = os.path.join(self.OUT_DIR, "ambari-server.out")
    self.SERVER_LOG_FILE = os.path.join(self.OUT_DIR, "ambari-server.log")
    self.ROOT_FS_PATH = os.sep

    self.JDK_INSTALL_DIR = ""
    self.JDK_SEARCH_PATTERN = ""
    self.JAVA_EXE_SUBPATH = ""
    self.JDK_SECURITY_DIR = os.path.join("jre", "lib", "security")
    self.SERVER_RESOURCES_DIR = ""

    # Configuration defaults
    self.DEFAULT_CONF_DIR = ""
    self.PID_DIR = os.sep + os.path.join("var", "run", "ambari-server")
    self.DEFAULT_LIBS_DIR = ""
    self.DEFAULT_VLIBS_DIR = ""

    self.AMBARI_PROPERTIES_BACKUP_FILE = ""
    self.AMBARI_KRB_JAAS_LOGIN_BACKUP_FILE = ""
    # ownership/permissions mapping
    # path - permissions - user - group - recursive
    # Rules are executed in the same order as they are listed
    # {0} in user/group will be replaced by customized ambari-server username
    self.NR_ADJUST_OWNERSHIP_LIST = []
    self.NR_CHANGE_OWNERSHIP_LIST = []
    self.NR_USERADD_CMD = ""

    self.MASTER_KEY_FILE_PERMISSIONS = "640"
    self.CREDENTIALS_STORE_FILE_PERMISSIONS = "640"
    self.TRUST_STORE_LOCATION_PERMISSIONS = "640"

    self.DEFAULT_DB_NAME = "ambari"

    self.STACK_LOCATION_DEFAULT = ""

    self.DEFAULT_VIEWS_DIR = ""

    #keytool commands
    self.keytool_bin_subpath = ""

    #Standard messages
    self.MESSAGE_SERVER_RUNNING_AS_ROOT = ""
    self.MESSAGE_ERROR_SETUP_NOT_ROOT = ""
    self.MESSAGE_ERROR_RESET_NOT_ROOT = ""
    self.MESSAGE_ERROR_UPGRADE_NOT_ROOT = ""
    self.MESSAGE_CHECK_FIREWALL = ""

@OsFamilyImpl(os_family=OSConst.WINSRV_FAMILY)
class ServerConfigDefaultsWindows(ServerConfigDefaults):
  def __init__(self):
    super(ServerConfigDefaultsWindows, self).__init__()
    self.JDK_INSTALL_DIR = "C:\\"
    self.JDK_SEARCH_PATTERN = "j[2se|dk|re]*"
    self.JAVA_EXE_SUBPATH = "bin\\java.exe"

    # Configuration defaults
    self.DEFAULT_CONF_DIR = "conf"
    self.DEFAULT_LIBS_DIR = "lib"

    self.AMBARI_PROPERTIES_BACKUP_FILE = "ambari.properties.backup"
    self.AMBARI_KRB_JAAS_LOGIN_BACKUP_FILE = ""  # ToDo: should be adjusted later
    # ownership/permissions mapping
    # path - permissions - user - group - recursive
    # Rules are executed in the same order as they are listed
    # {0} in user/group will be replaced by customized ambari-server username
    # The permissions are icacls
    self.NR_ADJUST_OWNERSHIP_LIST = [
      (self.OUT_DIR, "M", "{0}", True),  #0110-0100-0100 rw-r-r
      (self.OUT_DIR, "F", "{0}", False), #0111-0101-0101 rwx-rx-rx
      (self.PID_DIR, "M", "{0}", True),
      (self.PID_DIR, "F", "{0}", False),
      ("bootstrap", "F", "{0}", False),
      ("ambari-env.cmd", "F", "{0}", False),
      ("keystore", "M", "{0}", True),
      ("keystore", "F", "{0}", False),
      ("keystore\\db", "700", "{0}", False),
      ("keystore\\db\\newcerts", "700", "{0}", False),
      ("resources\\stacks", "755", "{0}", True),
      ("resources\\custom_actions", "755", "{0}", True),
      ("conf", "644", "{0}", True),
      ("conf", "755", "{0}", False),
      ("conf\\password.dat", "640", "{0}", False),
      # Also, /etc/ambari-server/conf/password.dat
      # is generated later at store_password_file
    ]
    self.NR_USERADD_CMD = "cmd /C net user {0} {1} /ADD"

    self.SERVER_RESOURCES_DIR = "resources"
    self.STACK_LOCATION_DEFAULT = "resources\\stacks"

    self.DEFAULT_VIEWS_DIR = "resources\\views"

    #keytool commands
    self.keytool_bin_subpath = "bin\\keytool.exe"

    #Standard messages
    self.MESSAGE_SERVER_RUNNING_AS_ROOT = "Ambari Server running with 'root' privileges."
    self.MESSAGE_ERROR_SETUP_NOT_ROOT = "Ambari-server setup must be run with administrator-level privileges"
    self.MESSAGE_ERROR_RESET_NOT_ROOT = "Ambari-server reset must be run with administrator-level privileges"
    self.MESSAGE_ERROR_UPGRADE_NOT_ROOT = "Ambari-server upgrade must be run with administrator-level privileges"
    self.MESSAGE_CHECK_FIREWALL = "Checking firewall status..."

@OsFamilyImpl(os_family=OsFamilyImpl.DEFAULT)
class ServerConfigDefaultsLinux(ServerConfigDefaults):
  def __init__(self):
    super(ServerConfigDefaultsLinux, self).__init__()
    # JDK
    self.JDK_INSTALL_DIR = "/usr/jdk64"
    self.JDK_SEARCH_PATTERN = "jdk*"
    self.JAVA_EXE_SUBPATH = "bin/java"

    # Configuration defaults
    self.DEFAULT_CONF_DIR = "/etc/ambari-server/conf"
    self.DEFAULT_LIBS_DIR = "/usr/lib/ambari-server"
    self.DEFAULT_VLIBS_DIR = "/var/lib/ambari-server"

    self.AMBARI_PROPERTIES_BACKUP_FILE = "ambari.properties.rpmsave"
    self.AMBARI_ENV_BACKUP_FILE = "ambari-env.sh.rpmsave"
    self.AMBARI_KRB_JAAS_LOGIN_BACKUP_FILE = "krb5JAASLogin.conf.rpmsave"
    # ownership/permissions mapping
    # path - permissions - user - group - recursive
    # Rules are executed in the same order as they are listed
    # {0} in user/group will be replaced by customized ambari-server username
    self.NR_ADJUST_OWNERSHIP_LIST = [
      ("/var/log/ambari-server/", "644", "{0}", True),
      ("/var/log/ambari-server/", "755", "{0}", False),
      ("/var/run/ambari-server/", "644", "{0}", True),
      ("/var/run/ambari-server/", "755", "{0}", False),
      ("/var/run/ambari-server/bootstrap", "755", "{0}", False),
      ("/var/lib/ambari-server/ambari-env.sh", "700", "{0}", False),
      ("/var/lib/ambari-server/ambari-sudo.sh", "700", "{0}", False),
      ("/var/lib/ambari-server/keys/", "600", "{0}", True),
      ("/var/lib/ambari-server/keys/", "700", "{0}", False),
      ("/var/lib/ambari-server/keys/db/", "700", "{0}", False),
      ("/var/lib/ambari-server/keys/db/newcerts/", "700", "{0}", False),
      ("/var/lib/ambari-server/keys/.ssh", "700", "{0}", False),
      ("/var/lib/ambari-server/resources/common-services/", "755", "{0}", True),
      ("/var/lib/ambari-server/resources/stacks/", "755", "{0}", True),
      ("/var/lib/ambari-server/resources/custom_actions/", "755", "{0}", True),
      ("/var/lib/ambari-server/resources/host_scripts/", "755", "{0}", True),
      ("/var/lib/ambari-server/resources/views/", "644", "{0}", True),
      ("/var/lib/ambari-server/resources/views/", "755", "{0}", False),
      ("/var/lib/ambari-server/resources/views/work/", "755", "{0}", True),
      ("/etc/ambari-server/conf/", "644", "{0}", True),
      ("/etc/ambari-server/conf/", "755", "{0}", False),
      ("/etc/ambari-server/conf/password.dat", "640", "{0}", False),
      ("/var/lib/ambari-server/keys/pass.txt", "600", "{0}", False),
      ("/etc/ambari-server/conf/ldap-password.dat", "640", "{0}", False),
      ("/var/run/ambari-server/stack-recommendations/", "744", "{0}", True),
      ("/var/run/ambari-server/stack-recommendations/", "755", "{0}", False),
      ("/var/lib/ambari-server/resources/data/", "644", "{0}", False),
      ("/var/lib/ambari-server/resources/data/", "755", "{0}", False),
      ("/var/lib/ambari-server/data/tmp/", "644", "{0}", True),
      ("/var/lib/ambari-server/data/tmp/", "755", "{0}", False),
      ("/var/lib/ambari-server/data/cache/", "600", "{0}", True),
      ("/var/lib/ambari-server/data/cache/", "700", "{0}", False),
      # Also, /etc/ambari-server/conf/password.dat
      # is generated later at store_password_file
    ]
    self.NR_CHANGE_OWNERSHIP_LIST = [
      ("/var/lib/ambari-server", "{0}", True),
      ("/usr/lib/ambari-server", "{0}", True),
      ("/var/log/ambari-server", "{0}", True),
      ("/var/run/ambari-server", "{0}", True),
      ("/etc/ambari-server", "{0}", True),
    ]
    self.NR_USERADD_CMD = 'useradd -M --comment "{1}" ' \
                 '--shell %s -d /var/lib/ambari-server/keys/ {0}' % locate_file('nologin', '/sbin')

    self.SERVER_RESOURCES_DIR = "/var/lib/ambari-server/resources"
    self.STACK_LOCATION_DEFAULT = "/var/lib/ambari-server/resources/stacks"

    self.DEFAULT_VIEWS_DIR = "/var/lib/ambari-server/resources/views"

    #keytool commands
    self.keytool_bin_subpath = "bin/keytool"

    #Standard messages
    self.MESSAGE_SERVER_RUNNING_AS_ROOT = "Ambari Server running with administrator privileges."
    self.MESSAGE_ERROR_SETUP_NOT_ROOT = "Ambari-server setup should be run with root-level privileges"
    self.MESSAGE_ERROR_RESET_NOT_ROOT = "Ambari-server reset should be run with root-level privileges"
    self.MESSAGE_ERROR_UPGRADE_NOT_ROOT = "Ambari-server upgrade must be run with root-level privileges"
    self.MESSAGE_CHECK_FIREWALL = "Checking firewall status..."

configDefaults = ServerConfigDefaults()

# Security
SECURITY_KEYS_DIR = "security.server.keys_dir"
SECURITY_MASTER_KEY_LOCATION = "security.master.key.location"
SECURITY_KEY_IS_PERSISTED = "security.master.key.ispersisted"
SECURITY_KEY_ENV_VAR_NAME = "AMBARI_SECURITY_MASTER_KEY"
SECURITY_MASTER_KEY_FILENAME = "master"
SECURITY_IS_ENCRYPTION_ENABLED = "security.passwords.encryption.enabled"
SECURITY_KERBEROS_JASS_FILENAME = "krb5JAASLogin.conf"

SECURITY_PROVIDER_GET_CMD = "{0} -cp {1} " + \
                            "org.apache.ambari.server.security.encryption" + \
                            ".CredentialProvider GET {2} {3} {4} " + \
                            "> " + configDefaults.SERVER_OUT_FILE + " 2>&1"

SECURITY_PROVIDER_PUT_CMD = "{0} -cp {1} " + \
                            "org.apache.ambari.server.security.encryption" + \
                            ".CredentialProvider PUT {2} {3} {4} " + \
                            "> " + configDefaults.SERVER_OUT_FILE + " 2>&1"

SECURITY_PROVIDER_KEY_CMD = "{0} -cp {1} " + \
                            "org.apache.ambari.server.security.encryption" + \
                            ".MasterKeyServiceImpl {2} {3} {4} " + \
                            "> " + configDefaults.SERVER_OUT_FILE + " 2>&1"



def get_conf_dir():
  try:
    conf_dir = os.environ[AMBARI_CONF_VAR]
    return conf_dir
  except KeyError:
    default_conf_dir = configDefaults.DEFAULT_CONF_DIR
    print_info_msg(AMBARI_CONF_VAR + " is not set, using default " + default_conf_dir)
    return default_conf_dir

def find_properties_file():
  conf_file = search_file(AMBARI_PROPERTIES_FILE, get_conf_dir())
  if conf_file is None:
    err = 'File %s not found in search path $%s: %s' % (AMBARI_PROPERTIES_FILE,
          AMBARI_CONF_VAR, get_conf_dir())
    print err
    raise FatalException(1, err)
  else:
    print_info_msg('Loading properties from ' + conf_file)
  return conf_file

# Load ambari properties and return dict with values
def get_ambari_properties():
  conf_file = find_properties_file()

  properties = None
  try:
    properties = Properties()
    properties.load(open(conf_file))
  except (Exception), e:
    print 'Could not read "%s": %s' % (conf_file, e)
    return -1
  return properties

def read_ambari_user():
  '''
  Reads ambari user from properties file
  '''
  properties = get_ambari_properties()
  if properties != -1:
    user = properties[NR_USER_PROPERTY]
    if user:
      return user
  return None

def get_value_from_properties(properties, key, default=""):
  try:
    value = properties.get_property(key)
    if not value:
      value = default
  except:
    return default
  return value

def get_views_dir(properties):
  views_dir = properties.get_property(VIEWS_DIR_PROPERTY)
  if views_dir is None or views_dir == "":
    views_dirs = glob.glob("/var/lib/ambari-server/resources/views/work")
  else:
    views_dirs = glob.glob(views_dir + "/work")
  return views_dirs

def get_admin_views_dir(properties):
  views_dir = properties.get_property(VIEWS_DIR_PROPERTY)
  if views_dir is None or views_dir == "":
    views_dirs = glob.glob("/var/lib/ambari-server/resources/views/work/ADMIN_VIEW*")
  else:
    views_dirs = glob.glob(views_dir + "/work/ADMIN_VIEW*")
  return views_dirs

def get_is_secure(properties):
  isSecure = properties.get_property(SECURITY_IS_ENCRYPTION_ENABLED)
  isSecure = True if isSecure and isSecure.lower() == 'true' else False
  return isSecure

def get_is_persisted(properties):
  keyLocation = get_master_key_location(properties)
  masterKeyFile = search_file(SECURITY_MASTER_KEY_FILENAME, keyLocation)
  isPersisted = True if masterKeyFile else False

  return (isPersisted, masterKeyFile)

def get_credential_store_location(properties):
  store_loc = properties[SECURITY_KEYS_DIR]
  if store_loc is None or store_loc == "":
    store_loc = "/var/lib/ambari-server/keys/credentials.jceks"
  else:
    store_loc += os.sep + "credentials.jceks"
  return store_loc

def get_master_key_location(properties):
  keyLocation = properties[SECURITY_MASTER_KEY_LOCATION]
  if keyLocation is None or keyLocation == "":
    keyLocation = properties[SECURITY_KEYS_DIR]
  return keyLocation

# Copy file to /tmp and save with file.# (largest # is latest file)
def backup_file_in_temp(filePath):
  if filePath is not None:
    tmpDir = tempfile.gettempdir()
    back_up_file_count = len(glob.glob1(tmpDir, AMBARI_PROPERTIES_FILE + "*"))
    try:
      shutil.copyfile(filePath, tmpDir + os.sep +
                      AMBARI_PROPERTIES_FILE + "." + str(back_up_file_count + 1))
    except (Exception), e:
      print_error_msg('Could not backup file in temp "%s": %s' % (
        back_up_file_count, str(e)))
  return 0

def get_ambari_version(properties):
  """
  :param properties: Ambari properties
  :return: Return a string of the ambari version. When comparing versions, please use "compare_versions" function.
  """
  version = None
  try:
    server_version_file_path = properties[SERVER_VERSION_FILE_PATH]
    if server_version_file_path and os.path.exists(server_version_file_path):
      with open(server_version_file_path, 'r') as file:
        version = file.read().strip()
  except:
    print_error_msg("Error getting ambari version")
  return version

def get_db_type(properties):
  """
  :rtype ServerDatabaseEntry
  """
  db_type = None
  persistence_type = properties[PERSISTENCE_TYPE_PROPERTY]

  if properties[JDBC_DATABASE_PROPERTY]:
    db_type = ServerDatabases.match(properties[JDBC_DATABASE_PROPERTY])
    if db_type == ServerDatabases.postgres and persistence_type == "local":
      db_type = ServerDatabases.postgres_internal

  if properties[JDBC_URL_PROPERTY] and db_type is None:
    jdbc_url = properties[JDBC_URL_PROPERTY].lower()
    if str(ServerDatabases.postgres) in jdbc_url:
      db_type = ServerDatabases.postgres
    elif str(ServerDatabases.oracle) in jdbc_url:
      db_type = ServerDatabases.oracle
    elif str(ServerDatabases.mysql) in jdbc_url:
      db_type = ServerDatabases.mysql
    elif str(ServerDatabases.mssql) in jdbc_url:
      db_type = ServerDatabases.mssql
    elif str(ServerDatabases.derby) in jdbc_url:
      db_type = ServerDatabases.derby
    elif str(ServerDatabases.sqlanywhere) in jdbc_url:
      db_type = ServerDatabases.sqlanywhere

  if persistence_type == "local" and db_type is None:
    db_type = ServerDatabases.postgres_internal

  return db_type

def check_database_name_property(upgrade=False):
  """
  :param upgrade: If Ambari is being upgraded.
  :return:
  """
  properties = get_ambari_properties()
  if properties == -1:
    print_error_msg("Error getting ambari properties")
    return -1

  version = get_ambari_version(properties)
  if upgrade and (properties[JDBC_DATABASE_PROPERTY] not in ServerDatabases.databases()
                    or properties.has_key(JDBC_RCA_SCHEMA_PROPERTY)):
    # This code exists for historic reasons in which property names changed from Ambari 1.6.1 to 1.7.0
    persistence_type = properties[PERSISTENCE_TYPE_PROPERTY]
    if persistence_type == "remote":
      db_name = properties[JDBC_RCA_SCHEMA_PROPERTY]  # this was a property in Ambari 1.6.1, but not after 1.7.0
      if db_name:
        write_property(JDBC_DATABASE_NAME_PROPERTY, db_name)

      # If DB type is missing, attempt to reconstruct it from the JDBC URL
      db_type = properties[JDBC_DATABASE_PROPERTY]
      if db_type is None or db_type.strip().lower() not in ServerDatabases.databases():
        db_type = get_db_type(properties).name
        if db_type:
          write_property(JDBC_DATABASE_PROPERTY, db_type)

      properties = get_ambari_properties()
    elif persistence_type == "local":
      # Ambari 1.6.1, had "server.jdbc.database" as the DB name, and the
      # DB type was assumed to be "postgres" if was embedded ("local")
      db_name = properties[JDBC_DATABASE_PROPERTY]
      if db_name:
        write_property(JDBC_DATABASE_NAME_PROPERTY, db_name)
        write_property(JDBC_DATABASE_PROPERTY, "postgres")
        properties = get_ambari_properties()

  dbname = properties[JDBC_DATABASE_NAME_PROPERTY]
  if dbname is None or dbname == "":
    err = "DB Name property not set in config file.\n" + SETUP_OR_UPGRADE_MSG
    raise FatalException(-1, err)

def update_database_name_property(upgrade=False):
  try:
    check_database_name_property(upgrade)
  except FatalException:
    properties = get_ambari_properties()
    if properties == -1:
      err = "Error getting ambari properties"
      raise FatalException(-1, err)
    print_warning_msg(JDBC_DATABASE_NAME_PROPERTY + " property isn't set in " +
                      AMBARI_PROPERTIES_FILE + ". Setting it to default value - " + configDefaults.DEFAULT_DB_NAME)
    properties.process_pair(JDBC_DATABASE_NAME_PROPERTY, configDefaults.DEFAULT_DB_NAME)
    conf_file = find_properties_file()
    try:
      properties.store(open(conf_file, "w"))
    except Exception, e:
      err = 'Could not write ambari config file "%s": %s' % (conf_file, e)
      raise FatalException(-1, err)


def encrypt_password(alias, password):
  properties = get_ambari_properties()
  if properties == -1:
    raise FatalException(1, None)
  return get_encrypted_password(alias, password, properties)

def get_encrypted_password(alias, password, properties):
  isSecure = get_is_secure(properties)
  (isPersisted, masterKeyFile) = get_is_persisted(properties)
  if isSecure:
    masterKey = None
    if not masterKeyFile:
      # Encryption enabled but no master key file found
      masterKey = get_original_master_key(properties)

    retCode = save_passwd_for_alias(alias, password, masterKey)
    if retCode != 0:
      print 'Failed to save secure password!'
      return password
    else:
      return get_alias_string(alias)

  return password


def is_alias_string(passwdStr):
  regex = re.compile("\$\{alias=[\w\.]+\}")
  # Match implies string at beginning of word
  r = regex.match(passwdStr)
  if r is not None:
    return True
  else:
    return False

def get_alias_string(alias):
  return "${alias=" + alias + "}"

def get_alias_from_alias_string(aliasStr):
  return aliasStr[8:-1]

def read_passwd_for_alias(alias, masterKey=""):
  if alias:
    jdk_path = find_jdk()
    if jdk_path is None:
      print_error_msg("No JDK found, please run the \"setup\" "
                      "command to install a JDK automatically or install any "
                      "JDK manually to " + configDefaults.JDK_INSTALL_DIR)
      return 1

    tempFileName = "ambari.passwd"
    passwd = ""
    tempDir = tempfile.gettempdir()
    #create temporary file for writing
    tempFilePath = tempDir + os.sep + tempFileName
    file = open(tempFilePath, 'w+')
    os.chmod(tempFilePath, stat.S_IREAD | stat.S_IWRITE)
    file.close()

    if masterKey is None or masterKey == "":
      masterKey = "None"

    command = SECURITY_PROVIDER_GET_CMD.format(get_java_exe_path(),
                                               get_full_ambari_classpath(), alias, tempFilePath, masterKey)
    (retcode, stdout, stderr) = run_os_command(command)
    print_info_msg("Return code from credential provider get passwd: " +
                   str(retcode))
    if retcode != 0:
      print 'ERROR: Unable to read password from store. alias = ' + alias
    else:
      passwd = open(tempFilePath, 'r').read()
      # Remove temporary file
    os.remove(tempFilePath)
    return passwd
  else:
    print_error_msg("Alias is unreadable.")

def decrypt_password_for_alias(properties, alias):
  isSecure = get_is_secure(properties)
  if isSecure:
    masterKey = None
    (isPersisted, masterKeyFile) = get_is_persisted(properties)
    if not masterKeyFile:
      # Encryption enabled but no master key file found
      masterKey = get_original_master_key(properties)

    return read_passwd_for_alias(alias, masterKey)
  else:
    return alias

def save_passwd_for_alias(alias, passwd, masterKey=""):
  if alias and passwd:
    jdk_path = find_jdk()
    if jdk_path is None:
      print_error_msg("No JDK found, please run the \"setup\" "
                      "command to install a JDK automatically or install any "
                      "JDK manually to " + configDefaults.JDK_INSTALL_DIR)
      return 1

    if masterKey is None or masterKey == "":
      masterKey = "None"

    command = SECURITY_PROVIDER_PUT_CMD.format(get_java_exe_path(),
                                               get_full_ambari_classpath(), alias, passwd, masterKey)
    (retcode, stdout, stderr) = run_os_command(command)
    print_info_msg("Return code from credential provider save passwd: " +
                   str(retcode))
    return retcode
  else:
    print_error_msg("Alias or password is unreadable.")


def get_pass_file_path(conf_file, filename):
  return os.path.join(os.path.dirname(conf_file), filename)

def store_password_file(password, filename):
  conf_file = find_properties_file()
  passFilePath = get_pass_file_path(conf_file, filename)

  with open(passFilePath, 'w+') as passFile:
    passFile.write(password)
  print_info_msg("Adjusting filesystem permissions")
  ambari_user = read_ambari_user()
  set_file_permissions(passFilePath, "660", ambari_user, False)

  #Windows paths need double backslashes, otherwise the Ambari server deserializer will think the single \ are escape markers
  return passFilePath.replace('\\', '\\\\')

def remove_password_file(filename):
  conf_file = find_properties_file()
  passFilePath = os.path.join(os.path.dirname(conf_file),
                              filename)

  if os.path.exists(passFilePath):
    try:
      os.remove(passFilePath)
    except Exception, e:
      print_warning_msg('Unable to remove password file: ' + str(e))
      return 1
  pass
  return 0


def get_original_master_key(properties):
  input = True
  while(input):
    try:
      masterKey = get_validated_string_input('Enter current Master Key: ',
                                             "", ".*", "", True, False)
    except KeyboardInterrupt:
      print 'Exiting...'
      sys.exit(1)

    # Find an alias that exists
    alias = None
    property = properties.get_property(JDBC_PASSWORD_PROPERTY)
    if property and is_alias_string(property):
      alias = JDBC_RCA_PASSWORD_ALIAS

    if not alias:
      property = properties.get_property(LDAP_MGR_PASSWORD_PROPERTY)
      if property and is_alias_string(property):
        alias = LDAP_MGR_PASSWORD_ALIAS

    if not alias:
      property = properties.get_property(SSL_TRUSTSTORE_PASSWORD_PROPERTY)
      if property and is_alias_string(property):
        alias = SSL_TRUSTSTORE_PASSWORD_ALIAS

    # Decrypt alias with master to validate it, if no master return
    if alias and masterKey:
      password = read_passwd_for_alias(alias, masterKey)
      if not password:
        print "ERROR: Master key does not match."
        continue

    input = False

  return masterKey


# Load database connection properties from conf file
def parse_properties_file(args):
  properties = get_ambari_properties()
  if properties == -1:
    print_error_msg("Error getting ambari properties")
    return -1

  args.server_version_file_path = properties[SERVER_VERSION_FILE_PATH]
  args.persistence_type = properties[PERSISTENCE_TYPE_PROPERTY]
  args.jdbc_url = properties[JDBC_URL_PROPERTY]

  args.dbms = properties[JDBC_DATABASE_PROPERTY]
  if not args.persistence_type:
    args.persistence_type = "local"

  if args.persistence_type == 'remote':
    args.database_host = properties[JDBC_HOSTNAME_PROPERTY]
    args.database_port = properties[JDBC_PORT_PROPERTY]

  args.database_name = properties[JDBC_DATABASE_NAME_PROPERTY]
  args.database_username = properties[JDBC_USER_NAME_PROPERTY]
  args.postgres_schema = properties[JDBC_POSTGRES_SCHEMA_PROPERTY] \
    if JDBC_POSTGRES_SCHEMA_PROPERTY in properties.propertyNames() else None
  args.database_password_file = properties[JDBC_PASSWORD_PROPERTY]
  if args.database_password_file:
    if not is_alias_string(args.database_password_file):
      args.database_password = open(properties[JDBC_PASSWORD_PROPERTY]).read()
    else:
      args.database_password = args.database_password_file
  return 0

def is_jaas_keytab_exists(conf_file):
  with open(conf_file, "r") as f:
    lines = f.read()

  match = re.search("keyTab=(.*)$", lines, re.MULTILINE)
  return os.path.exists(match.group(1).strip("\"").strip())

def update_krb_jaas_login_properties():
  """
  Update configuration files
  :return: int -2 - skipped, -1 - error, 0 - successful
  """
  prev_conf_file = search_file(configDefaults.AMBARI_KRB_JAAS_LOGIN_BACKUP_FILE, get_conf_dir())
  conf_file = search_file(AMBARI_KRB_JAAS_LOGIN_FILE, get_conf_dir())

  # check if source and target files exists, if not - skip copy action
  if prev_conf_file is None or conf_file is None:
    return -2

  # if rpmsave file contains invalid keytab, we can skip restoring
  if not is_jaas_keytab_exists(prev_conf_file):
    return -2

  try:
    # restore original file, destination arg for rename func shouldn't exists
    os.remove(conf_file)
    os.rename(prev_conf_file, conf_file)
    print_warning_msg("Original file %s kept" % AMBARI_KRB_JAAS_LOGIN_FILE)
  except OSError as e:
    print "Couldn't move %s file: %s" % (prev_conf_file, e)
    return -1

  return 0

def update_ambari_env():
  prev_env_file = search_file(configDefaults.AMBARI_ENV_BACKUP_FILE, configDefaults.DEFAULT_VLIBS_DIR)
  env_file = search_file(AMBARI_ENV_FILE, configDefaults.DEFAULT_VLIBS_DIR)

  # Previous env file does not exist
  if (not prev_env_file) or (prev_env_file is None):
    print_warning_msg("Can not find %s file from previous version, skipping restore of environment settings" %
                      configDefaults.AMBARI_ENV_BACKUP_FILE)
    return 0

  try:
    if env_file is not None:
      os.remove(env_file)
      os.rename(prev_env_file, env_file)
      print_warning_msg("Original file %s kept" % AMBARI_ENV_FILE)
  except OSError as e:
    print "Couldn't move %s file: %s" % (prev_env_file, e)
    return -1

  return 0

def update_ambari_properties():
  prev_conf_file = search_file(configDefaults.AMBARI_PROPERTIES_BACKUP_FILE, get_conf_dir())
  conf_file = search_file(AMBARI_PROPERTIES_FILE, get_conf_dir())

  # Previous config file does not exist
  if (not prev_conf_file) or (prev_conf_file is None):
    print_warning_msg("Can not find %s file from previous version, skipping import of settings" % configDefaults.AMBARI_PROPERTIES_BACKUP_FILE)
    return 0

  # ambari.properties file does not exists
  if conf_file is None:
    print_error_msg("Can't find %s file" % AMBARI_PROPERTIES_FILE)
    return -1

  try:
    old_properties = Properties()
    old_properties.load(open(prev_conf_file))
  except Exception, e:
    print 'Could not read "%s": %s' % (prev_conf_file, e)
    return -1

  try:
    new_properties = Properties()
    new_properties.load(open(conf_file))

    for prop_key, prop_value in old_properties.getPropertyDict().items():
      if "agent.fqdn.service.url" == prop_key:
        # BUG-7179 what is agent.fqdn property in ambari.props?
        new_properties.process_pair(GET_FQDN_SERVICE_URL, prop_value)
      elif "server.os_type" == prop_key:
        new_properties.process_pair(OS_TYPE_PROPERTY, OS_FAMILY + OS_VERSION)
      else:
        new_properties.process_pair(prop_key, prop_value)

    # Adding custom user name property if it is absent
    # In previous versions without custom user support server was started as
    # "root" anyway so it's a reasonable default
    if NR_USER_PROPERTY not in new_properties.keys():
      new_properties.process_pair(NR_USER_PROPERTY, "root")

    if OS_FAMILY_PROPERTY not in new_properties.keys():
      new_properties.process_pair(OS_FAMILY_PROPERTY, OS_FAMILY + OS_VERSION)

    new_properties.store(open(conf_file, 'w'))

  except Exception, e:
    print 'Could not write "%s": %s' % (conf_file, e)
    return -1

  timestamp = datetime.datetime.now()
  fmt = '%Y%m%d%H%M%S'
  os.rename(prev_conf_file, prev_conf_file + '.' + timestamp.strftime(fmt))

  return 0

# update properties in a section-less properties file
# Cannot use ConfigParser due to bugs in version 2.6
def update_properties(propertyMap):
  conf_file = search_file(AMBARI_PROPERTIES_FILE, get_conf_dir())
  backup_file_in_temp(conf_file)
  if propertyMap is not None and conf_file is not None:
    properties = Properties()
    try:
      with open(conf_file, 'r') as file:
        properties.load(file)
    except (Exception), e:
      print_error_msg('Could not read "%s": %s' % (conf_file, e))
      return -1

    for key in propertyMap.keys():
      properties.removeOldProp(key)
      properties.process_pair(key, str(propertyMap[key]))

    for key in properties.keys():
      if not propertyMap.has_key(key):
        properties.removeOldProp(key)

    with open(conf_file, 'w') as file:
      properties.store_ordered(file)

  return 0

def update_properties_2(properties, propertyMap):
  conf_file = search_file(AMBARI_PROPERTIES_FILE, get_conf_dir())
  backup_file_in_temp(conf_file)
  if conf_file is not None:
    if propertyMap is not None:
      for key in propertyMap.keys():
        properties.removeOldProp(key)
        properties.process_pair(key, str(propertyMap[key]))
      pass

    with open(conf_file, 'w') as file:
      properties.store_ordered(file)
    pass
  pass

def write_property(key, value):
  conf_file = find_properties_file()
  properties = Properties()
  try:
    properties.load(open(conf_file))
  except Exception, e:
    print_error_msg('Could not read ambari config file "%s": %s' % (conf_file, e))
    return -1
  properties.process_pair(key, value)
  try:
    properties.store(open(conf_file, "w"))
  except Exception, e:
    print_error_msg('Could not write ambari config file "%s": %s' % (conf_file, e))
    return -1
  return 0

#
# Checks if options determine local DB configuration
#
def is_local_database(args):
  try:
    return args.persistence_type == 'local'
  except AttributeError:
    return False


def update_debug_mode():
  debug_mode = get_debug_mode()
  # The command-line settings supersede the ones in ambari.properties
  if not debug_mode & 1:
    properties = get_ambari_properties()
    if properties == -1:
      print_error_msg("Error getting ambari properties")
      return -1

    if get_value_from_properties(properties, DEBUG_MODE_KEY, False):
      debug_mode = debug_mode | 1
    if get_value_from_properties(properties, SUSPEND_START_MODE_KEY, False):
      debug_mode = debug_mode | 2

    set_debug_mode(debug_mode)

#
### JDK ###
#

#
# Describes the JDK configuration data, necessary for download and installation
#
class JDKRelease:
  name = ""
  desc = ""
  url = ""
  dest_file = ""
  jcpol_url = "http://public-repo-1.hortonworks.com/ARTIFACTS/UnlimitedJCEPolicyJDK7.zip"
  dest_jcpol_file = ""
  inst_dir = ""

  def __init__(self, i_name, i_desc, i_url, i_dest_file, i_jcpol_url, i_dest_jcpol_file, i_inst_dir, i_reg_exp):
    if i_name is None or i_name is "":
      raise FatalException(-1, "Invalid JDK name: " + (i_desc or ""))
    self.name = i_name
    if i_desc is None or i_desc is "":
      self.desc = self.name
    else:
      self.desc = i_desc
    if i_url is None or i_url is "":
      raise FatalException(-1, "Invalid URL for JDK " + i_name)
    self.url = i_url
    if i_dest_file is None or i_dest_file is "":
      self.dest_file = i_name + ".exe"
    else:
      self.dest_file = i_dest_file
    if not (i_jcpol_url is None or i_jcpol_url is ""):
      self.jcpol_url = i_jcpol_url
    if i_dest_jcpol_file is None or i_dest_jcpol_file is "":
      self.dest_jcpol_file = "jcpol-" + i_name + ".zip"
    else:
      self.dest_jcpol_file = i_dest_jcpol_file
    if i_inst_dir is None or i_inst_dir is "":
      self.inst_dir = os.path.join(configDefaults.JDK_INSTALL_DIR, i_desc)
    else:
      self.inst_dir = i_inst_dir
    if i_reg_exp is None or i_reg_exp is "":
      raise FatalException(-1, "Invalid output parsing regular expression for JDK " + i_name)
    self.reg_exp = i_reg_exp

  @classmethod
  def from_properties(cls, properties, section_name):
    (desc, url, dest_file, jcpol_url, jcpol_file, inst_dir, reg_exp) = JDKRelease.__load_properties(properties, section_name)
    cls = JDKRelease(section_name, desc, url, dest_file, jcpol_url, jcpol_file, inst_dir, reg_exp)
    return cls

  @staticmethod
  def __load_properties(properties, section_name):
    if section_name is None or section_name is "":
      raise FatalException(-1, "Invalid properties section: " + ("(empty)" if section_name is None else ""))
    if(properties.has_key(section_name + ".desc")):   #Not critical
      desc = properties[section_name + ".desc"]
    else:
      desc = section_name
    if not properties.has_key(section_name + ".url"):
      raise FatalException(-1, "Invalid JDK URL in the properties section: " + section_name)
    url = properties[section_name + ".url"]      #Required
    if not properties.has_key(section_name + ".re"):
      raise FatalException(-1, "Invalid JDK output parsing regular expression in the properties section: " + section_name)
    reg_exp = properties[section_name + ".re"]      #Required
    if(properties.has_key(section_name + ".dest-file")):   #Not critical
      dest_file = properties[section_name + ".dest-file"]
    else:
      dest_file = section_name + ".exe"
    if(properties.has_key(section_name + ".jcpol-url")):   #Not critical
      jcpol_url = properties[section_name + ".jcpol-url"]
    else:
      jcpol_url = None
    if(properties.has_key(section_name + ".jcpol-file")):   #Not critical
      jcpol_file = properties[section_name + ".jcpol-file"]
    else:
      jcpol_file = None
    if(properties.has_key(section_name + ".home")):   #Not critical
      inst_dir = properties[section_name + ".home"]
    else:
      inst_dir = "C:\\" + section_name
    return (desc, url, dest_file, jcpol_url, jcpol_file, inst_dir, reg_exp)
  pass

def get_ambari_jars():
  try:
    conf_dir = os.environ[AMBARI_SERVER_LIB]
    return conf_dir
  except KeyError:
    default_jar_location = configDefaults.DEFAULT_LIBS_DIR
    print_info_msg(AMBARI_SERVER_LIB + " is not set, using default "
                 + default_jar_location)
    return default_jar_location

def get_jdbc_cp():
  jdbc_jar_path = ""
  properties = get_ambari_properties()
  if properties != -1:
    jdbc_jar_path = properties[JDBC_DRIVER_PATH_PROPERTY]
  return jdbc_jar_path

def get_ambari_classpath():
  ambari_cp = os.path.abspath(get_ambari_jars() + os.sep + "*")
  jdbc_cp = get_jdbc_cp()
  if len(jdbc_cp) > 0:
    ambari_cp = ambari_cp + os.pathsep + jdbc_cp
  return ambari_cp

def get_full_ambari_classpath(conf_dir = None):
  if conf_dir is None:
    conf_dir = get_conf_dir()
  cp = conf_dir + os.pathsep + get_ambari_classpath()
  if cp.find(' ') != -1:
    cp = '"' + cp + '"'
  return cp

def get_JAVA_HOME():
  properties = get_ambari_properties()
  if properties == -1:
    print_error_msg("Error getting ambari properties")
    return None

  java_home = properties[JAVA_HOME_PROPERTY]

  if (not 0 == len(java_home)) and (os.path.exists(java_home)):
    return java_home

  return None

#
# Checks jdk path for correctness
#
def validate_jdk(jdk_path):
  if jdk_path:
    if os.path.exists(jdk_path):
      java_exe_path = os.path.join(jdk_path, configDefaults.JAVA_EXE_SUBPATH)
      if os.path.exists(java_exe_path) and os.path.isfile(java_exe_path):
        return True
  return False

#
# Finds the available JDKs.
#
def find_jdk():
  jdkPath = get_JAVA_HOME()
  if jdkPath:
    if validate_jdk(jdkPath):
      return jdkPath
  print "Looking for available JDKs at " + configDefaults.JDK_INSTALL_DIR
  jdks = glob.glob(os.path.join(configDefaults.JDK_INSTALL_DIR, configDefaults.JDK_SEARCH_PATTERN))
  #[fbarca] Use the newest JDK
  jdks.sort(None, None, True)
  print "Found: " + str(jdks)
  if len(jdks) == 0:
    return
  for jdkPath in jdks:
    print "Trying to use JDK {0}".format(jdkPath)
    if validate_jdk(jdkPath):
      print "Selected JDK {0}".format(jdkPath)
      return jdkPath
    else:
      print "JDK {0} is invalid".format(jdkPath)
  return

def get_java_exe_path():
  jdkPath = find_jdk()
  if jdkPath:
    java_exe = os.path.join(jdkPath, configDefaults.JAVA_EXE_SUBPATH)
    return java_exe
  return


#
# Server resource files location
#
def get_resources_location(properties):
  err = 'Invalid directory'
  try:
    resources_dir = properties[RESOURCES_DIR_PROPERTY]
    if not resources_dir:
      resources_dir = configDefaults.SERVER_RESOURCES_DIR
  except (KeyError), e:
    err = 'Property ' + str(e) + ' is not defined at ' + properties.fileName
    resources_dir = configDefaults.SERVER_RESOURCES_DIR

  if not os.path.exists(os.path.abspath(resources_dir)):
    msg = 'Resources dir ' + resources_dir + ' is incorrectly configured: ' + err
    raise FatalException(1, msg)

  return resources_dir

#
# Stack upgrade
#
def get_stack_location(properties):
  stack_location = properties[STACK_LOCATION_KEY]
  if stack_location is None:
    stack_location = configDefaults.STACK_LOCATION_DEFAULT
  return stack_location
