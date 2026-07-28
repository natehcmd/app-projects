#!/bin/zsh
cd "$(dirname "$0")"
(sleep 1 && open http://localhost:8444) &
exec node server.js
