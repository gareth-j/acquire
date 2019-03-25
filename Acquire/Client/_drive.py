
__all__ = ["Drive"]


def _get_storage_url():
    """Function to discover and return the default storage url"""
    return "http://fn.acquire-aaai.com:8080/t/storage"


def _get_storage_service(storage_url=None):
    """Function to return the storage service for the system"""
    if storage_url is None:
        storage_url = _get_storage_url()

    from Acquire.Client import Service as _Service
    service = _Service(storage_url)

    if not service.is_storage_service():
        from Acquire.Client import LoginError
        raise LoginError(
            "You can only use a valid storage service to get CloudDrive info! "
            "The service at '%s' is a '%s'" %
            (storage_url, service.service_type()))

    if service.service_url() != storage_url:
        service.update_service_url(storage_url)

    return service


def _create_drive(user, name, drivemeta, storage_service):
    """Internal function used to create a Drive"""
    from Acquire.Client import ACLRule as _ACLRule
    drive = Drive()
    drive._name = drivemeta.name()
    drive._drive_uid = drivemeta.uid()
    drive._container = drivemeta.container_uids()
    drive._acl = drivemeta.acl()
    drive._user = user
    drive._storage_service = storage_service
    return drive


def _get_drive(user, name=None, storage_service=None, storage_url=None,
               autocreate=True):
    """Return the drive called 'name' of the passed user. Note that the
       user must be authenticated to call this function. The name
       will default to 'main' if it is not set, and the drive will
       be created automatically is 'autocreate' is True and the
       drive does not exist
    """
    if storage_service is None:
        storage_service = _get_storage_service(storage_url)
    else:
        if not storage_service.is_storage_service():
            raise TypeError("You can only query drives using "
                            "a valid storage service")

    if name is None:
        name = "main"
    else:
        name = str(name)

    if autocreate:
        autocreate = True
    else:
        autocreate = False

    from Acquire.Client import Authorisation as _Authorisation
    authorisation = _Authorisation(resource="UserDrives", user=user)

    args = {"authorisation": authorisation.to_data(),
            "name": name, "autocreate": autocreate}

    response = storage_service.call_function(function="open_drive", args=args)

    from Acquire.Client import DriveMeta as _DriveMeta

    return _create_drive(user=user, name=name, storage_service=storage_service,
                         drivemeta=_DriveMeta.from_data(response["drive"]))


class Drive:
    """This class provides a handle to a user's drive (space
       to hold files and folders). A drive is associated with
       a single storage service and can be shared amongst several
       users. Each drive has a unique UID, with users assiging
       their own shorthand names.
    """
    def __init__(self, user=None, name=None, storage_service=None,
                 storage_url=None, autocreate=True):
        """Construct a handle to the drive that the passed user
           calls 'name' on the passed storage service. If
           'autocreate' is True and the user is logged in then
           this will automatically create the drive if
           it doesn't exist already
        """
        if user is not None:
            drive = _get_drive(user=user, name=name,
                               storage_service=storage_service,
                               storage_url=storage_url, autocreate=autocreate)

            from copy import copy as _copy
            self.__dict__ = _copy(drive.__dict__)
        else:
            self._drive_uid = None

    def __str__(self):
        if self.is_null():
            return "Drive::null"
        else:
            return "Drive(user='%s', name='%s')" % \
                    (self._user.username(), self.name())

    def is_null(self):
        """Return whether or not this drive is null"""
        return self._drive_uid is None

    def acl(self):
        """Return the access control list for the user on this drive"""
        if self.is_null():
            from Acquire.Client import ACLRule as _ACLRule
            return _ACLRule.null()
        else:
            return self._acl

    def name(self):
        """Return the name given to this drive by the user"""
        return self._name

    def uid(self):
        """Return the UID of this drive"""
        return self._drive_uid

    def guid(self):
        """Return the global UID of this drive (combination of the
           UID of the storage service and UID of the drive)
        """
        if self.is_null():
            return None
        else:
            return "%s@%s" % (self.storage_service().uid(), self.uid())

    def storage_service(self):
        """Return the storage service for this drive"""
        if self.is_null():
            return None
        else:
            return self._storage_service

    def upload(self, filename, aclrule=None):
        """Upload the file at 'filename' to this drive. This will overwrite
           any existing file, as long as we have permission to do so.
           The file will be uploaded to drive/filename (will eventually
           make this more configurable!)
        """
        if self.is_null():
            raise PermissionError("Cannot upload a file to a null drive!")

        from Acquire.Client import Authorisation as _Authorisation
        from Acquire.Client import FileHandle as _FileHandle
        from Acquire.Client import PAR as _PAR
        from Acquire.Client import FileMeta as _FileMeta

        filehandle = _FileHandle(filename=filename, drive_uid=self.uid(),
                                 aclrule=aclrule)

        authorisation = _Authorisation(
                            resource="upload %s" % filehandle.fingerprint(),
                            user=self._user)

        args = {"filehandle": filehandle.to_data(),
                "authorisation": authorisation.to_data()}

        if not filehandle.is_localdata():
            # we will need to upload against a PAR, so need to tell
            # the service how to encrypt the PAR...
            privkey = self._user.session_key()
            args["encryption_key"] = privkey.public_key().to_data()

        # will eventually need to authorise payment...

        response = self.storage_service().call_function(
                                function="upload_file", args=args)

        # if this was a large file, then we will receive a PAR back
        # which must be used to upload the file
        if not filehandle.is_localdata():
            par = _PAR.from_data(response["upload_par"])
            par.write(privkey).set_object_from_file(
                                    filehandle.local_filename())

            authorisation = _Authorisation(
                                resource="uploaded %s" % par.uid(),
                                user=self._user)

            args = {"drive_uid": self.uid(),
                    "authorisation": authorisation.to_data(),
                    "par_uid": par.uid()}

            response = self.storage_service().call_function(
                                      function="uploaded_file", args=args)

        filemeta = _FileMeta.from_data(response["filemeta"])

        return filemeta

    @staticmethod
    def _list_drives(user, drive_uid=None,
                     storage_service=None, storage_url=None):
        if storage_service is None:
            storage_service = _get_storage_service(storage_url)
        else:
            if not storage_service.is_storage_service():
                raise TypeError("You can only query drives using "
                                "a valid storage service")

        from Acquire.Client import Authorisation as _Authorisation
        authorisation = _Authorisation(resource="UserDrives", user=user)

        args = {"authorisation": authorisation.to_data()}

        if drive_uid is not None:
            args["drive_uid"] = str(drive_uid)

        response = storage_service.call_function(
                                    function="list_drives", args=args)

        from Acquire.ObjectStore import string_to_list as _string_to_list
        from Acquire.Client import DriveMeta as _DriveMeta

        return _string_to_list(response["drives"], _DriveMeta)

    @staticmethod
    def list_toplevel_drives(user, storage_service=None, storage_url=None):
        """Return a list of all of the DriveMetas of the drives accessible
           at the top-level by the passed user on the passed storage
           service
        """
        return Drive._list_drives(user=user,
                                  storage_service=storage_service,
                                  storage_url=storage_url)

    def list_drives(self):
        """Return a list of the DriveMetas of all of the drives contained
           in this drive that are accessible to the user
        """
        if self.is_null():
            return []
        else:
            return Drive._list_drives(user=self._user,
                                      drive_uid=self._drive_uid,
                                      storage_service=self._storage_service)

    def list_files(self):
        """Return a list of the FileMetas of all of the files contained
           in this drive
        """
        if self.is_null():
            return []

        from Acquire.Client import Authorisation as _Authorisation
        from Acquire.ObjectStore import string_to_list as _string_to_list
        from Acquire.Storage import FileMeta as _FileMeta

        authorisation = _Authorisation(resource="list_files",
                                       user=self._user)

        args = {"authorisation": authorisation.to_data(),
                "drive_uid": self._drive_uid}

        response = self.storage_service().call_function(function="list_files",
                                                        args=args)

        return _string_to_list(response["files"], _FileMeta)
