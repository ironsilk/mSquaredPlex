#!/bin/bash

jq '."script-torrent-done-enabled" = true' /config/settings.json
jq '."script-torrent-done-filename" = "/torr_finished_routine.sh"' /config/settings.json
# test 1231
jq '."incomplete-dir-enabled" = false' /config/settings.json

