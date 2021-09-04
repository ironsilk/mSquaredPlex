#!/bin/bash

jq '."script-torrent-done-enabled" = true' /defaults/settings.json
jq '."script-torrent-done-filename" = "/torr_finished_routine.sh"' /defaults/settings.json
jq '."incomplete-dir-enabled" = "false"' /defaults/settings.json
