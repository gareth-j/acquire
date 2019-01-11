
import os as _os
import uuid as _uuid

from ._request import Request as _Request
from ._checksum import get_filesize_and_checksum as _get_filesize_and_checksum

from ._errors import RunRequestError

__all__ = ["RunRequest"]


def _get_abspath_size_md5(basedir, key, filename, max_size=None):
    """Assert that the specified filename associated with key 'key' exists
       and is readable by this user. Assert also that the filesize if below
       'size' bytes, is 'max_size' has been specified. This returns the
       absolute filename path for the file, the size of the file in bytes
       and the md5 checksum of the file, as a tuple
    """

    if _os.path.isabs(filename):
        filename = _os.path.realpath(filename)
    else:
        filename = _os.path.realpath(_os.path.join(basedir, filename))

    try:
        FILE = open(filename, "r")
        FILE.close()
    except Exception as e:
        raise RunRequestError(
            "Cannot complete the run request because the file '%s' is not "
            "readable: filename=%s, error=%s" % (key, filename, str(e)))

    (filesize, md5) = _get_filesize_and_checksum(filename)

    if filesize > max_size:
        raise RunRequestError(
            "Cannot complete the run request because the file '%s' is "
            "too large: filename=%s, filesize=%f MB, max_size=%f MB" %
            (key, filename, filesize/(1024.0*1024.0),
             max_size/(1024.0*1024.0)))

    return (filename, filesize, md5)


class RunRequest(_Request):
    """This class holds a request to run a particular calculation
       on a RunService. The result of this request will be a
       PAR to which the input should be loaded, and a Bucket
       from which the output can be read. The calculation will
       start once the input has been signalled as loaded.
    """
    def __init__(self, runfile=None):
        """Construct the request
        """
        super().__init__()

        self._uid = None
        self._runinfo = None
        self._tarfile = None
        self._tarfilename = None
        self._tarsize = None
        self._tarmd5 = None

        if runfile is not None:
            # Package up the simulation described in runfile
            self._set_runfile(runfile)

    def is_null(self):
        """Return whether or not this is a null request"""
        return self._uid is None

    def __str__(self):
        if self.is_null():
            return "RunRequest::null"
        else:
            return "RunRequest(uid=%s)" % self._uid

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._uid == other._uid
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def uid(self):
        """Return the UID of this request"""
        return self._uid

    def tarfile(self):
        """Return the name of the tarfile containing all of the
           input files
        """
        return self._tarfilename

    def tarfile_size(self):
        """Return the size of the tarfile in bytes"""
        return self._tarsize

    def tarfile_md5sum(self):
        """Return the MD5 checksum of the tarfile containing
           the input files"""
        return self._tarmd5

    def runinfo(self):
        """Return the processed run information used to describe the
           calculation to be run. This includes information about all
           of the input files, such as their names, filesizes and
           MD5 checksums
        """
        import copy as _copy
        return _copy.deepcopy(self._runinfo)

    def input_files(self):
        """Return a dictionary of the input file information for the
           input files for the calculation. This is a dictionary mapping
           the key for each file to the filename in the tarfile, the
           size of the file in the tarfile and the md5 sum of the file
        """
        if self._runinfo is None:
            return None

        if "input" in self._runinfo:
            return self._runinfo["input"]
        else:
            return None

    def _validate_input(self, basedir, runinfo):
        """Validate that the passed input 'runinfo' is correct, given
           it was loaded from the directory 'basedir'. This
           makes sure that all of the input files exist and are readable
           relative to 'basedir'. These MUST be declared in the 'input'
           section of the dictionary. This returns an updated 'runinfo'
           which has all relative paths converted to absolute file paths
        """
        if "input" not in runinfo:
            return runinfo

        try:
            items = runinfo["input"][0].items()
        except:
            try:
                items = runinfo["input"].items()
            except:
                raise RunRequestError(
                    "Cannot execute the request because the input files "
                    "are specified with the wrong format. They should be "
                    "a single dictionary of key-value pairs. "
                    "Instead it is '%s'" % str(runinfo["input"]))

        input = {}

        for (key, filename) in items:
            # check the file exists and is not more than 100 MB is size
            (absfile, filesize, md5) = _get_abspath_size_md5(
                                                basedir, key,
                                                filename,
                                                100*1024*1024)

            input[key] = (absfile, filesize, md5)

        runinfo["input"] = input

        return runinfo

    def _create_tarfile(self):
        """This function creates the new tarfile and updates the
           runinfo with the paths for the input files in the zipfile
        """
        if self._tarfile is not None:
            raise RunRequestError("You cannot create the tarfile twice...")

        if "input" not in self._runinfo:
            return

        input = self._runinfo["input"]

        import tarfile as _tarfile
        import tempfile as _tempfile

        # loop through each file - add it to tarbz2. The files are added
        # flat into the tar.bz2, i.e. with no subdirectory. This is to
        # prevent strange complications or clashes with other files that
        # the user may create during output (on the server the files will
        # be unpacked into a uniquely-named directory)
        names = {}

        tempfile = _tempfile.NamedTemporaryFile(suffix="tar.bz2")
        tarfile = _tarfile.TarFile(fileobj=tempfile, mode="w")

        for (key, fileinfo) in input.items():
            (filename, filesize, md5) = fileinfo

            name = _os.path.basename(filename)

            # make sure that there isn't a matching file in the tarfile
            i = 0
            while name in names:
                i += 1
                name = "%d_%s" % (i, name)

            tarfile.add(name=filename, arcname=name, recursive=False)

            input[key] = (name, filesize, md5)

        tarfile.close()

        # close the file so that it is written to the disk - if we close
        # the tempfile then the file is deleted... (which shouldn't happen
        # until the object is deleted)
        tempfile.file.close()

        self._tarfile = tempfile
        self._tarfilename = tempfile.name

        (filesize, md5) = _get_filesize_and_checksum(tempfile.name)

        self._tarsize = filesize
        self._tarmd5 = md5

    def _set_runfile(self, runfile):
        """Run the simulation described in the passed runfile (should
           be in yaml or json format). This gives the type of simulation, the
           location of the input files and how the output should be
           named
        """
        if self._runinfo:
            raise RunRequestError(
                "You cannot change runfile of this RunRequest")

        if runfile is None:
            return

        runlines = None

        try:
            with open(runfile, "r") as FILE:
                runlines = FILE.read()
        except Exception as e:
            raise RunRequestError(
                "Cannot read '%s'. You must supply a readable input file "
                "that describes the calculation to be performed and supplies "
                "the names of all of the input files. Error = %s" %
                (runfile, str(e)))

        # get the directory that contains this file
        basedir = _os.path.dirname(_os.path.abspath(runfile))

        # try to parse this input as yaml
        runinfo = None

        try:
            import yaml as _yaml
            runinfo = _yaml.safe_load(runlines)
        except:
            pass

        if runinfo is None:
            try:
                import json as _json
                runinfo = _json.loads(runlines)
            except:
                pass

        if runinfo is None:
            raise RunRequestError(
                "Cannot interpret valid input read from the file '%s'. "
                "This should be in json or yaml format, and this parser "
                "be built with that support." % runfile)

        runinfo = self._validate_input(basedir, runinfo)
        self._runinfo = runinfo

        self._create_tarfile()

        # everything is ok - set the UID of this request
        self._uid = str(_uuid.uuid4())

    def signature(self):
        """Return a signature that uniquely defines this request"""
        return "%s=%s" % (self.uid(), self.tarfile_md5sum())

    def to_data(self):
        """Return this request as a json-serialisable dictionary"""
        if self.is_null():
            return {}

        data = super().to_data()
        data["uid"] = self._uid
        data["runinfo"] = self._runinfo
        data["tarsize"] = self._tarsize
        data["tarmd5"] = self._tarmd5

        return data

    @staticmethod
    def from_data(data):
        if (data and len(data) > 0):
            r = RunRequest()

            r._uid = data["uid"]
            r._runinfo = data["runinfo"]
            r._tarsize = int(data["tarsize"])
            r._tarmd5 = data["tarmd5"]

            super()._from_data(data)

            return r

        return None
