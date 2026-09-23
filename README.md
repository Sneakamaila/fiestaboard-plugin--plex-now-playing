# Plex Now Playing Plugin for FiestaBoard

Displays the currently playing movie or TV episode from your Plex Media Server on your Vestaboard.

## How It Works
The plugin polls your Plex Media Server "/status/sessions" endpoint. It picks the first active session and exposes movie or episode metadata.

## Installation
curl -X POST http://YOUR-IP:4420/api/plugins/install -H "Content-Type: application/json" -d '{"repository": "https://github.com/Sneakamaila/fiestaboard-plugin--plex-now-playing"}'
