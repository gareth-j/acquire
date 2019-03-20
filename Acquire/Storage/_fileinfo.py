
__all__ = ["FileInfo", "VersionInfo"]

_version_root = "storage/version"

_fileinfo_root = "storage/file"

_file_root = "storage/file"


class VersionInfo:
    """This class holds specific info about a version of a file"""
    def __init__(self, filesize=None, checksum=None,
                 acls=None, user_guid=None):
        """Construct the version of the file that has the passed
           size and checksum, was uploaded by the specified user,
           and that has the specified acls
        """
        if filesize is not None:
            from Acquire.ObjectStore import create_uuid as _create_uuid
            from Acquire.ObjectStore import get_datetime_now \
                as _get_datetime_now
            from Acquire.ObjectStore import datetime_to_string \
                as _datetime_to_string
            from Acquire.Storage import ACLRule as _ACLRule

            self._filesize = filesize
            self._checksum = checksum
            self._file_uid = _create_uuid()
            self._user_guid = str(user_guid)

            self._acls = {}

            if acls is not None:
                for user, acl in acls.items():
                    if not isinstance(acl, _ACLRule):
                        raise TypeError(
                            "ACL must be of type ACLRule")

                    if user is not None:
                        self._acls[str(user)] = acl
                    else:
                        self._acls[user] = acl

            self._datetime = _get_datetime_now()

        else:
            self._filesize = None

    def is_null(self):
        """Return whether or not this is null"""
        return self._filesize is None

    def filesize(self):
        """Return the size in bytes of this version of the file"""
        if self.is_null():
            return 0
        else:
            return self._filesize

    def checksum(self):
        """Return the checksum for this version of the file"""
        if self.is_null():
            return None
        else:
            return self._checksum

    def acl(self, user_guid):
        """Return the ACL for this version of the file for the user
           with passed GUID. This ACL will override any ACL inherited
           from the drive
        """
        try:
            return self._acls[user_guid]
        except:
            from Acquire.Storage import ACLRule as _ACLRule
            return _ACLRule.inherit()

    def uid(self):
        """Return the UID of this version of the file in object store"""
        if self.is_null():
            return None
        else:
            return self._file_uid

    def datetime(self):
        """Return the datetime when this version was created"""
        if self.is_null():
            return self._datetime
        else:
            return None

    def uploaded_by(self):
        """Return the GUID of the user that uploaded this version"""
        if self.is_null():
            return self._user_guid
        else:
            return None

    def _file_key(self):
        """Return the key for this actual file for this version
           in the object store"""
        if self.is_null():
            return None
        else:
            from Acquire.ObjectStore import datetime_to_string \
                as _datetime_to_string

            return "%s/%s/%s" % (_file_root,
                                 _datetime_to_string(self._datetime),
                                 self._file_uid)

    def _key(self, drive_uid, encoded_filename):
        """Return the key for this version in the object store"""
        if self.is_null():
            return None
        else:
            from Acquire.ObjectStore import datetime_to_string \
                as _datetime_to_string
            return "%s/%s/%s/%s/%s" % (
                _version_root, drive_uid, encoded_filename,
                _datetime_to_string(self._datetime), self._file_uid)

    def to_data(self):
        """Return a json-serialisable dictionary for this object"""
        data = {}

        if not self.is_null():
            from Acquire.ObjectStore import datetime_to_string \
                as _datetime_to_string
            from Acquire.ObjectStore import dict_to_string \
                as _dict_to_string
            data["filesize"] = self._filesize
            data["checksum"] = self._checksum
            data["file_uid"] = self._file_uid
            data["datetime"] = _datetime_to_string(self._datetime)
            data["user_guid"] = self._user_guid
            data["acls"] = _dict_to_string(self._acls)

        return data

    @staticmethod
    def from_data(data):
        """Return this object constructed from the passed json-deserialised
           dictionary
        """
        v = VersionInfo()

        if data is not None and len(data) > 0:
            from Acquire.ObjectStore import string_to_datetime \
                as _string_to_datetime
            from Acquire.ObjectStore import string_to_dict \
                as _string_to_dict
            from Acquire.Storage import ACLRule as _ACLRule
            v._filesize = data["filesize"]
            v._checksum = data["checksum"]
            v._file_uid = data["file_uid"]
            v._user_guid = data["user_guid"]
            v._datetime = _string_to_datetime(data["datetime"])
            v._acls = _string_to_dict(data["acls"], _ACLRule)

        return v


class FileInfo:
    """This class provides information about a user-file that has
       been uploaded to the storage service. This includes all
       versions of the file, the ACLs for different users etc.

       Just as Acquire.Client.Drive provides the client-side view
       of Acquire.Storage.DriveInfo, so to does
       Acquire.Client.FileHandle provide the client-side view
       of Acquire.Storage.FileInfo
    """
    def __init__(self, drive_uid=None, filehandle=None, user_guid=None):
        """Construct from a passed filehandle of a file that will be
           uploaded
        """
        self._filename = None

        if filehandle is not None:
            from Acquire.Client import FileHandle as _FileHandle

            if not isinstance(filehandle, _FileHandle):
                raise TypeError(
                    "The filehandle must be of type FileHandle")

            if filehandle.is_null():
                return

            self._drive_uid = drive_uid

            from Acquire.ObjectStore import string_to_encoded \
                as _string_to_encoded
            from Acquire.ObjectStore import string_to_filepath \
                as _string_to_filepath

            self._filename = _string_to_filepath(filehandle.remote_filename())
            self._encoded_filename = _string_to_encoded(self._filename)

            version = VersionInfo(filesize=filehandle.filesize(),
                                  checksum=filehandle.checksum(),
                                  user_guid=user_guid,
                                  acls=None)

            self._latest_version = version

            # save this to the object store
            self.save()

    def is_null(self):
        """Return whether or not this is null"""
        return self._filename is None

    def filename(self):
        """Return the object-store filename for this file"""
        return self._filename

    def _version_info(self, version=None):
        """Return the version info object of the latest version of
           the file, or the passed version
        """
        if self.is_null():
            return VersionInfo()
        else:
            if version is None:
                return self._latest_version

            from Acquire.Storage import MissingVersionError
            raise MissingVersionError(
                "Cannot find the version '%s' for file '%s'" %
                (version, self.filename()))

    def filesize(self, version=None):
        """Return the size (in bytes) of the latest (or specified)
           version of this file"""
        return self._version_info(version=version).filesize()

    def checksum(self, version=None):
        """Return the checksum of the latest (or specified) version
           of this file
        """
        return self._version_info(version=version).checksum()

    def drive_uid(self):
        """Return the UID of the drive on which this file resides"""
        return self._drive_uid

    def drive(self):
        """Return the actual DriveInfo object for the drive on which this
           file resides
        """
        if self.is_null():
            return None
        else:
            from Acquire.Storage import DriveInfo as _DriveInfo
            return _DriveInfo(drive_uid=self.drive_uid())

    def file_uid(self, version=None):
        """Return the UID of the latest (or specified) version
           of this file
        """
        return self._version_info(version=version).uid()

    def acl(self, version=None, user_guid=None):
        """Return the ACL rule for the specified user, or if that is not
           specified, the ACL mask that will be applied to the ACL
           for the drive
        """
        return self._version_info(version=version).acl(user_guid=user_guid)

    def version(self, version):
        """Return the version at the specified datetime"""
        return self._version_info(version=version)

    def latest_version(self):
        """Return the latest version of this file on the storage service. This
           is a datetime of the upload of the latest version. You will need to
           use the 'versions' function to find if there are other versions.
        """
        if self.is_null():
            return None
        else:
            return self._latest_version

    def versions(self):
        """Return the sorted list of all versions of this file on the
           storage service
        """
        if self.is_null():
            return []
        else:
            return {self._latest_version.datetime(), self._latest_version}

    def _fileinfo_key(self):
        """Return the key for this fileinfo in the object store"""
        return "%s/%s/%s" % (_fileinfo_root, self._drive_uid,
                             self._encoded_filename)

    def save(self):
        """Save this fileinfo to the object store"""
        if self.is_null():
            return

        from Acquire.ObjectStore import ObjectStore as _ObjectStore

        metadata_bucket = self.drive()._get_metadata_bucket()

        # save the version information (saves old versions)
        _ObjectStore.set_object_from_json(
                        bucket=metadata_bucket,
                        key=self._latest_version._key(self._drive_uid,
                                                      self._encoded_filename),
                        data=self._latest_version.to_data())

        # save the fileinfo itself
        _ObjectStore.set_object_from_json(bucket=metadata_bucket,
                                          key=self._fileinfo_key(),
                                          data=self.to_data())

    @staticmethod
    def load(drive, filename):
        """Load and return the FileInfo for the file called 'filename'
           on the passed 'drive'"""
        from Acquire.Storage import DriveInfo as _DriveInfo

        if not isinstance(drive, _DriveInfo):
            raise TypeError("The drive must be of type DriveInfo")

        from Acquire.ObjectStore import ObjectStore as _ObjectStore
        from Acquire.ObjectStore import string_to_encoded \
            as _string_to_encoded

        metadata_bucket = drive._get_metadata_bucket()

        try:
            data = _ObjectStore.get_object_from_json(bucket=metadata_bucket,
                                                     key=self._filinfo_key())
        except:
            data = None

        if data is None:
            from Acquire.Storage import MissingFileError
            raise MissingFileError(
                "Cannnot find the file called '%s' on drive '%s'" %
                (filename, drive))

        f = FileInfo.from_data(data)
        f._drive_uid = drive.drive_uid()

        return f

    def to_data(self):
        """Return a json-serialisable dictionary for this object"""
        data = {}

        if not self.is_null():
            data["filename"] = self.filename()
            data["latest_version"] = self.latest_version().to_data()

        return data

    @staticmethod
    def from_data(data):
        """Return this object constructed from the passed json-deserialised
           dictionary
        """
        f = FileInfo()

        if data is not None and len(data) > 0:
            f._filename = data["filename"]
            f._latest_version = VersionInfo.from_data(data["latest_version"])
            f._drive_uid = None

        return f
