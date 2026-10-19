#!/bin/sh
# The container's entrypoint. Started as root only to give the app user /data (a host's
# persistent disk or a volume can be mounted root-owned, and then the session database can't be
# opened; a plain directory in the image is already the app user's, so nothing changes), then
# it drops to that user and execs the server: nothing else runs as root.
set -eu

if [ "$(id -u)" = 0 ]; then
    # only what isn't the app user's already (normally just the mount point itself)
    find /data -xdev ! -user compass -exec chown compass:compass {} +
    exec gosu compass "$@"
fi
exec "$@"
