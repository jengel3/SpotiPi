from __future__ import unicode_literals
import socketio
import eventlet
from flask import Flask, render_template, request

import sys
import threading
import os

import spotify
import random

import json
from pprint import pprint
from random import randrange

sio = socketio.Server()
app = Flask(__name__)

session = spotify.Session()
playingList = None
playing= None
lastTrack = None
isPaused = False

loop = spotify.EventLoop(session)
loop.start()

audio = spotify.AlsaSink(session)

logged_in = threading.Event()
end_of_track = threading.Event()

dir = os.path.dirname(__file__)
with open(os.path.join(dir, 'config.json')) as data_file:
    config = json.load(data_file)

username = config['username']
password = config['password']

if username == None or password == None:
    print "Username and password variables not set."
    sys.exit(0)

def make_track_json(track):
    tr = {}
    tr['name'] = track.name

    al = track.album
    album = {}
    album['name'] = al.name
    album['artist'] = al.artist.name
    album['cover'] = al.cover_link().url
    tr['album'] = album

    ar = track.artists[0]
    artist = {'name': ar.name}
    tr['artist'] = artist

    tr['duration'] = track.duration
    tr['popularity'] = track.popularity
    tr['uri'] = track.link.uri
    return tr

def make_tracks_json(raw):
    tracks = []
    for track in raw:
        tr = make_track_json(track)
        tracks.append(tr)
    return tracks

def make_playlists_json(lists):
    newls = []
    for l in lists:
        nl = {}
        name = l.name
        if name == None: continue
        nl['name'] = name
        nl['track_count'] = len(l.tracks)
        nl['uri'] = l.link.uri
        newls.append(nl)
    return newls


def do_search(query):
    con = spotify.Search(session, query)
    con.load()
    raw = con.tracks
    tracks = make_tracks_json(raw)
    return tracks

@app.route('/')
def index():
    print(request.headers.get('User-Agent'))
    return render_template('index.html')

@sio.on('connect')
def connect(sid, environ):
    print("connect ", sid)
    js = do_search('my house')
    sio.emit('data', json.dumps({'type': 'tracks', 'data': {'tracks': js}}))

@sio.on('action')
def message(sid, raw):
    js = raw
    action = js['action']
    data = js.get('data', None)
    global isPaused
    global playingList
    if action == 'play':
        global playing
        dtr = data.get('track', None) if data else None
        plist = data.get('playlist', None) if data else None
        if dtr:
            track = session.get_track(dtr).load()
            playing = track
            playingList = None
            session.player.load(track)
            session.player.play()
            raw = {'action': 'playing', 'data': {'paused': False}}
            raw['data']['track'] = make_track_json(track)
            sio.emit('action', json.dumps(raw))
        elif plist:
            playlist = session.get_playlist(plist)
            playlist.load()
            playingList = playlist
            index = randrange(0, len(playlist.tracks))
            track = playlist.tracks[index]
            track.load()
            playing = track
            session.player.load(track)
            session.player.play()
            raw = {'action': 'playing', 'data': {'paused': False, 'is_playlist': True}}
            raw['data']['track'] = make_track_json(track)
            sio.emit('action', json.dumps(raw))
        else:
            session.player.play()
            isp = (playingList == None)
            raw = {'action': 'playing', 'data': {'paused': False}}
            raw['data']['track'] = make_track_json(playing)
            sio.emit('action', json.dumps(raw))
    elif action == 'pause':
        isPaused = True
        session.player.pause()
        sio.emit('action', json.dumps({'action': 'paused'}))
    elif action == 'stop':
        playing = None
        playingList = None
        session.player.unload()
        sio.emit('action', json.dumps({'action': 'stopped'}))
    elif action == 'search':
        query = data['query']
        tracks = do_search(query)
        print("called")
        sio.emit('data', json.dumps({'type': 'tracks', 'data': {'tracks': tracks}}))
    elif action == 'playlists':
        user = session.get_user('spotify:user:{}'.format(username))
        user.load()
        playlists = user.published_playlists
        pls = make_playlists_json(playlists)
        print(pls)
        sio.emit('data', json.dumps({'type': 'playlists', 'data': {'playlists': pls}}))
    elif action == 'update':
        if playing == None: return
        isp = (playingList != None)
        raw = {'action': 'playing', 'data': {'paused': isPaused, 'track': make_track_json(playing), 'is_playlist': isp}}
        sio.emit('action', json.dumps(raw))
    elif action == 'skip':
        if playingList == None: return
        playlist = playingList
        playlist.load()
        index = randrange(0, len(playlist.tracks))
        track = playlist.tracks[index]
        track.load()
        session.player.load(track)
        session.player.play()
        playing = track
        raw = {'action': 'playing', 'data': {'paused': False, 'is_playlist': True}}
        raw['data']['track'] = make_track_json(track)
        sio.emit('action', json.dumps(raw))
    elif action == 'back':
        pass
    else:
        pass

def on_connection_state_updated(session):
    if session.connection.state is spotify.ConnectionState.LOGGED_IN:
        print "Successfully logged into Spotify"
        logged_in.set()
    elif session.connection.state is spotify.ConnectionState.LOGGED_OUT:
        print "Could not login to Spotify"
        sys.exit(0)
    elif session.connection.state is spotify.ConnectionState.DISCONNECTED:
        print "Disconnected from Spotify session"


def on_end_of_track(self):
    sio.emit('action', json.dumps({'action': 'stopped'}))
    end_of_track.set()
    playing = None
    session.player.unload()
    if playingList:
        print "Will play next song"
        tracks = playingList.tracks
        track = random.choice(tracks).load()
        playing = track
        print "Playing {}".format(track.name)
        session.player.load(track)
        session.player.play()

def on_playback_stop(session):
    sio.emit('action', json.dumps({'action': 'stopped'}))


session.on(spotify.SessionEvent.CONNECTION_STATE_UPDATED, on_connection_state_updated)
session.on(spotify.SessionEvent.END_OF_TRACK, on_end_of_track)
session.on(spotify.SessionEvent.STOP_PLAYBACK, on_playback_stop)


# session.on(spotify.SessionEvent.START_PLAYBACK, on_playback_start)

session.login(username, password, remember_me=True)
logged_in.wait()

app = socketio.Middleware(sio, app)
eventlet.wsgi.server(eventlet.listen(('', 3000)), app)