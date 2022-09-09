import argparse
import collections
import configparser
import hashlib
import os
import re
import string
import sys
import zlib



argparser = argparse.ArgumentParser(description="The stupid content tracker")
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True
argsp = argsubparsers.add_parser("init", help="Initialize new empty repo")

argsp.add_argument(
    "path",
    metavar="directory",
    nargs="?",
    default=".",
    help="where to create repo"

)

argsp = argsubparsers.add_parser(
    "hash-object",
    help="Compute object ID and optionally creates a blob from a file")

argsp.add_argument("-t",
                   metavar="type",
                   dest="type",
                   choices=["blob", "commit", "tag", "tree"],
                   default="blob",
                   help="Specify the type")

argsp.add_argument("-w",
                   dest="write",
                   action="store_true",
                   help="Actually write the object into the database")

argsp.add_argument("path",
                   help="Read object from <file>")

def cmd_init(args):
    

    return repo_create(args.path)


def repo_path(repo, *path):
    """Compute path under github repo dir """
    return os.path.join(repo.gitdir , *path)

#create dirname if absent 
def repo_file(repo , *path, mkdir=False):
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)

# mkdir path if absent and mkdir
def repo_dir(repo, *path, mkdir=False):
    path = repo_path(repo, *path)

    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        else:
            raise Exception("This is not a directory")
    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None

def repo_create(path):
    repo = GitRepository(path, True)

    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception(f"Not a directory {path}")
        if os.listdir(repo.worktree):        
            raise Exception(f"Not empty {path}")
    else:
        os.makedirs(repo.worktree)

    assert(repo_dir(repo, "branches", mkdir=True))
    assert(repo_dir(repo, "objects", mkdir=True ))
    assert(repo_dir(repo, "refs" , "tags", mkdir=True ))
    assert(repo_dir(repo, "refs" , "heads", mkdir=True ))

    # .git/description
    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unamed repository : edit this file description to name the repo")

    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")

    with open(repo_file(repo, "config") , "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo
        

def repo_default_config():
    ret = configparser.ConfigParser()

    ret.add_section("core")
    ret.set("core" , "repositoryformatversion" , "0")
    ret.set("core", "filemode", "false")
    ret.set("core" , "bare" , "false")

    return ret

def repo_find(path=".", required=True):
    path = os.path.realpath(path)

    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)
    parent = os.path.realpath(os.path.join(path, ".."))

    if parent == path:
        if required:
            raise Exception("No git dir")
        else:
            return None
    
    return repo_find(parent, required)




def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)

    if   args.command == "add"         : cmd_add(args)
    elif args.command == "cat-file"    : cmd_cat_file(args)
    elif args.command == "checkout"    : cmd_checkout(args)
    elif args.command == "commit"      : cmd_commit(args)
    elif args.command == "hash-object" : cmd_hash_object(args)
    elif args.command == "init"        : cmd_init(args)
    elif args.command == "log"         : cmd_log(args)
    elif args.command == "ls-tree"     : cmd_ls_tree(args)
    elif args.command == "merge"       : cmd_merge(args)
    elif args.command == "rebase"      : cmd_rebase(args)
    elif args.command == "rev-parse"   : cmd_rev_parse(args)
    elif args.command == "rm"          : cmd_rm(args)
    elif args.command == "show-ref"    : cmd_show_ref(args)
    elif args.command == "tag"         : cmd_tag(args)

class GitRepository(object):
    """ a git repo"""

    worktree = None
    gitdir = None
    conf = None

    def __init__(self, path, force=False) -> None:
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")
        
        if not (force or os.path.isdir(self.gitdir)):
            out = f"Not a git repo {path}"
            raise Exception(out)

        #read config file in .git/config
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Config file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception("Unsupported repository version")

class GitObject (object):
    repo = None

    def __init__(self, repo , data=None) -> None:
        self.repo = repo

        if data != None:
            self.deserialize(data)
    def deserialize(self):
        pass

    def serialize(self):
        """Must be implemented by subclass 
        read contents from self.data and convert to meaningful repr

        """
        pass

def object_read(repo, sha):
    # read object object id from git repo return a gitobject whose exact type depends on the object

    path = repo_file(repo, "objects" , sha[0:2], sha[2:])
    with open (path, "rb") as f:
        raw = zlib.decompress(f.read())

        # read obj type
        x = raw.find(b'')
        fmt = raw[0:x]

        #read and validate obj size
        y = raw.find(b'\x00', x)
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw)-y-1:
            raise Exception("malformed object bad length")

        #pick constructor
        if fmt==b'commit' : c=GitCommit
        elif fmt==b'tree' : c=GitTree
        elif fmt==b'tag'  : c =GitTag
        elif fmt==b'blob' : c=GitBlob
        else:
            raise Exception("Unkown type foro object")

        return c(repo, raw[y+1:])

def object_find(repo, name, fmt=None, follow=True):
    return name

def object_write(obj, actually_write=True):
    # serialize object data

    data = obj.serialize()
    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
    sha = hashlib.sha1(result).hexdigest()

    if actually_write:
        # compute path
        path = repo_file(obj.repo, "objects" , sha[0:2], sha[2:])

        with open(path, 'wb') as f:
           f.write(zlib.compress(result))

    return sha

class GitBlob(GitObject):
    fmt = b'blob'

    def serialize(self, blobdata):
        return self.blobdata

    def deserialize(self, data):
        self.data = data


def cmd_hash_object(args):
    if args.write:
        repo = GitRepository(".")
    else:
        repo = None

    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha) 

def object_hash(fd, fmt, repo=None):
    data = fd.read()

    if fmt==b'commit' : obj=GitCommit(repo, data)
    elif fmt==b'tree' : obj=GitTree(repo , data)
    elif fmt==b'tag'  : obj=GitTag(repo, data)
    elif fmt==b'blob' : obj=GitBlob(repo, data)
    else:
        raise Exception("Unknown type %s" % fmt% fmt% fmt% fmt% fmt)
    return object_write(obj, repo)

# maybe add support for git packfiles later

def kvlm_parse(raw , start=0, dict=None):
    if not dict:
        dict = collections.OrderedDict()

    spc = raw.find(b' ', start)

    nl = raw.find(b'\n', start)

    if (spc < 0) or (nl < spc):
        assert(nl == start)
        dict[b''] = raw[start+1:]
        return dict

    key = raw[start:spc]

    end = start
    while True:
        end = raw.find(b'\n', end+1)
        if raw[end+1] != ord(' ') : break

    value = raw[spc+1:end].replace(b'\n' , b'\n')

    if key in dict:
        if type(dict[key]) == list:
            dict[key].append(value)
        else:
            dict[key] = [dict[key], value]
    else:
        dict[key] = value
    return kvlm_parse(raw, start=end+1, dict=dict)

def kvlm_serialize(kvlm):
    ret = b''

    for k in kvlm.keys():
        if k == b'':
            continue
        val = kvlm[k]
        if type(val) != list:
            val = [val]

        for v in val:
            ret += k + b' ' + (v.replace(b'\n' , b'\n')) + b'\n'

    ret += b'\n' + kvlm[b'']

    return ret

class GitCommit(GitObject):
    fmt = b'commit'

    def __init__(self, repo, data=None) -> None:
        super().__init__(repo, data)

    def deserialize(self, data):
        self.kvlm = kvlm_parse(data)

    def serialize(self):
        return kvlm_serialize(self.kvlm)

argsp = argsubparsers.add_parser("log", help="Display history of a given commit.")
argsp.add_argument("commit",
                   default="HEAD",
                   nargs="?",
                   help="Commit to start at.")

def cmd_log(args):
    repo = repo_find()

    print("digraph wyalog{")

    log_graphviz(repo, object_find(repo, args.commit), set())

def log_graphviz(repo, sha, seen):
    if sha in seen:
        return

    seen.add(sha)
    commit = object_read(repo, sha)
    assert(commit.fmt==b'commit')

    if not b'parent' in commit.kvlm.keys():
        return
    parents = commit.kvlm[b'parent']
    if type(parents) != list:
        parents = [parents]

    for p in parents:
        p = p.decode("acii")
        print(f"c_{sha} -> c_{p}")
        log_graphviz(repo, p, seen)