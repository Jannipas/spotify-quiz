import spotipy
from spotipy.oauth2 import SpotifyOAuth
from flask import Flask, render_template_string, redirect, url_for, request, session, jsonify
import re
import os
import time
import json

# 1. FLASK-ANWENDUNG INITIALISIEREN
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')

# Scope kann global bleiben
scope = "user-read-currently-playing user-modify-playback-state"

# --- EINSTELLUNGEN ZUM ANPASSEN ---
highlight_color = "#C06EF3"
button_hover_color = "#983BD2"
wave_animation_speed = 50
polling_interval_seconds = 3
arrow_size = "60px"
arrow_thickness = 4
progress_bar_thickness = 10
album_art_hover_scale = 1.03
arrow_hover_scale = 1.15
button_hover_scale = 1.05
progress_bar_hover_increase_px = 3
# --- ENDE DER EINSTELLUNGEN ---


# Konstante für den Session-Key
TOKEN_INFO_KEY = 'spotify_token_info'

### 🧠 HELFER-FUNKTIONEN FÜR DIE AUTHENTIFIZIERUNG ###

def create_spotify_oauth():
    """Erstellt eine SpotifyOAuth-Instanz und liest die Konfiguration aus den Umgebungsvariablen."""
    return SpotifyOAuth(
        client_id=os.environ.get('CLIENT_ID'),
        client_secret=os.environ.get('CLIENT_SECRET'),
        redirect_uri=os.environ.get('REDIRECT_URI'),
        scope=scope,
        cache_path=None
    )

def get_token():
    """Holt das Token aus der Session, falls vorhanden, und erneuert es bei Bedarf."""
    token_info = session.get(TOKEN_INFO_KEY, None)
    if not token_info:
        return None

    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60
    if is_expired:
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session[TOKEN_INFO_KEY] = token_info
        
    return token_info

def get_spotify_client():
    """Erstellt einen Spotipy-Client, wenn der Nutzer angemeldet ist."""
    token_info = get_token()
    if not token_info:
        return None
    return spotipy.Spotify(auth=token_info['access_token'])


### 🚀 ROUTEN ###

@app.route("/login")
def login():
    """Leitet den Nutzer zur Spotify-Anmeldeseite weiter."""
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route("/logout")
def logout():
    """Meldet den Nutzer ab, indem die Session geleert wird."""
    session.pop(TOKEN_INFO_KEY, None)
    session.pop('quiz_state', None)
    session.pop('player_mode', None)
    return redirect(url_for('home'))

@app.route("/callback")
def callback():
    """Wird von Spotify nach der Anmeldung aufgerufen."""
    sp_oauth = create_spotify_oauth()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    
    
    # --- DEBUG-SPION 1 ---
    print("--- TOKEN WIRD IN CALLBACK GESPEICHERT ---")
    if token_info:
        print(f"Access Token endet auf: ...{token_info['access_token'][-6:]}")
        print(f"Refresh Token endet auf: ...{token_info['refresh_token'][-6:]}")
    print("---------------------------------------")
    # --- ENDE SPION 1 ---

    
    session[TOKEN_INFO_KEY] = token_info
    return redirect(url_for('home'))


@app.route("/")
def home():

    
    # --- DEBUG-SPION 2 ---
    token_in_session = session.get(TOKEN_INFO_KEY)
    print("\n--- TOKEN WIRD IN HOME GELESEN ---")
    if token_in_session:
        print(f"Access Token endet auf: ...{token_in_session['access_token'][-6:]}")
        print(f"Refresh Token endet auf: ...{token_in_session['refresh_token'][-6:]}")
    else:
        print("Kein Token in der Session gefunden.")
    print("--------------------------------\n")
    # --- ENDE SPION 2 ---

    
    sp = get_spotify_client()
    if not sp:
        # Login-Seite mit angepasstem Stil für bessere mobile Darstellung
        login_html = f"""
        <!DOCTYPE html><html lang="de"><head><meta charset="UTF-8"><title>Login</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background-color: #121212;
                color: #B3B3B3;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: flex-start;
                min-height: 100vh;
                margin: 0;
                text-align: center;
                padding-top: 5vh;
                padding-bottom: 5vh;
            }}
            .container {{
                width: calc(100% - 2rem);
                max-width: 600px;
                padding: 3rem;
                border-radius: 12px;
                background-color: #1a1a1a;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
            }}
            h1 {{
                color: #FFFFFF;
                font-size: clamp(1.5rem, 6vw, 2.5rem);
                margin-bottom: 2rem;
            }}
            .button {{
                padding: 12px 24px;
                background-color: {highlight_color};
                color: white;
                text-decoration: none;
                border-radius: 50px;
                font-weight: bold;
                transition: background-color 0.3s, transform 0.3s;
                display: inline-block;
            }}
            .button:hover {{
                background-color: {button_hover_color};
                transform: scale(1.05);
            }}
        </style></head><body><div class="container">
            <h1>Spotify Song Quiz</h1>
            <a href="/login" class="button">Mit Spotify anmelden</a>
        </div></body></html>"""
        return render_template_string(login_html)

    try:
        is_player_mode = session.get('player_mode', False)
        
        current_track = sp.currently_playing()
        if not current_track or not current_track.get('item'):
            raise ValueError("Kein abspielbarer Song gefunden.")

        current_track_id = current_track['item']['id']
        
        quiz_state = session.get('quiz_state', {})
        
        if current_track_id != quiz_state.get('track_id'):
            quiz_state = {'track_id': current_track_id, 'is_solved': False}
            session['quiz_state'] = quiz_state
            
        show_solution = is_player_mode or quiz_state.get('is_solved', False)
        
        progress_ms = current_track.get('progress_ms', 0)
        duration_ms = current_track['item'].get('duration_ms', 0)
        is_playing = current_track.get('is_playing', False)

        display_title = "Welcher Song ist das?"
        display_artist = "Wer ist der Interpret?"
        year_question_html = f'<h3 class="year-question">Aus welchem Jahr?</h3>'
        info_section_html = ""
        button_text = "Auflösen"
        button_link = "/solve"
        player_mode_checked = 'checked' if is_player_mode else ''

        image_html = f"""
        <div class="placeholder-quiz">
            <svg class="quiz-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
        </div>
        """

        track_name_raw = current_track["item"]["name"]
        artists_string = ", ".join([artist["name"] for artist in current_track["item"]["artists"]])
        album_name = current_track["item"]["album"]["name"]
        initial_release_year = int(current_track["item"]["album"]["release_date"].split('-')[0])
        album_image_url = "https://via.placeholder.com/300/1a1a1a?text=Error"
        if current_track["item"]["album"]["images"]:
            album_image_url = current_track["item"]["album"]["images"][0]["url"]

        if show_solution:
            display_title = track_name_raw
            display_artist = artists_string
            year_question_html = ""
            button_text = "Nächstes Lied"
            button_link = "/next"
            image_html = f'<img class="album-art" src="{album_image_url}" alt="Album Cover">'

            original_release_year = initial_release_year
            original_album_name = album_name
            
            terms_to_remove = [
                r"\s*-\s*\d{4}\s*Remaster.*", r"\s*-\s*Remastered\s*\d{4}",
                r"\(Remastered\)", r"\[Remastered\]", r"\s*-\s*Live", r"\(Live\)", 
                r"\(Edit\)", r"\s*-\s*Single Version"
            ]
            
            cleaned_track_name = track_name_raw
            for pattern in terms_to_remove: 
                cleaned_track_name = re.sub(pattern, "", cleaned_track_name, flags=re.IGNORECASE).strip()
            
            results = sp.search(q=f"track:{cleaned_track_name} artist:{artists_string}", type="track", limit=50)
            for result in results['tracks']['items']:
                try:
                    result_track_name_raw = result['name']
                    cleaned_result_track_name = result_track_name_raw
                    for pattern in terms_to_remove:
                        cleaned_result_track_name = re.sub(pattern, "", cleaned_result_track_name, flags=re.IGNORECASE).strip()

                    if cleaned_track_name.lower() == cleaned_result_track_name.lower():
                        result_year = int(result['album']['release_date'].split('-')[0])
                        if result_year < original_release_year:
                            original_release_year = result_year
                            original_album_name = result['album']['name']
                except (KeyError, ValueError): 
                    continue

            initial_year_html = ""
            original_info_html = ""
            prominent_year_html = f'<p class="prominent-year">{initial_release_year}</p>'
            if original_release_year < initial_release_year or track_name_raw != cleaned_track_name:
                prominent_year_html = f'<p class="prominent-year">{original_release_year}</p>'
                initial_year_html = f'<p><strong>Veröffentlichungsjahr:</strong> {initial_release_year}</p>'
                original_info_html = f"""<div class="info-box"><h3>Originalversion</h3><p><strong>Original-Titel für Suche:</strong> {cleaned_track_name}</p><p><strong>Original-Album:</strong> {original_album_name}</p></div>"""
            
            info_section_html = f"""
            <div class="info-section">
                <hr class="info-divider">
                <div class="info-box">
                    <p><strong>Album:</strong> {album_name}</p>
                    {initial_year_html}
                </div>
                {original_info_html}
                {prominent_year_html}
            </div>
            """
        
        html_content = f"""
        <!DOCTYPE html><html lang="de"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Spotify Song Quiz</title>
        <style>
            * {{ box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #121212; color: #B3B3B3; display: flex; flex-direction: column; align-items: center;justify-content: flex-start;min-height: 100vh; margin: 0; text-align: center;padding-top: 5vh;padding-bottom: 5vh;}}
            .container {{ width: calc(100% - 2rem); max-width: 600px; padding: 2rem; border-radius: 12px; background-color: #1a1a1a; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5); }}
            .album-art-container {{ display: flex; align-items: center; justify-content: center; gap: 20px; width: 100%; max-width: 450px; margin: 0 auto 1.5rem; }}
            .album-art-link {{ flex: 1 1 0; min-width: 0; display: flex; justify-content: center; transition: transform 0.3s ease; }}
            .album-art-link:hover {{ transform: scale({album_art_hover_scale}); }}
            .album-art, .placeholder-quiz {{ width: 100%; max-width: 300px; height: auto; aspect-ratio: 1 / 1; border-radius: 8px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3); }}
            .placeholder-quiz {{ display: flex; align-items: center; justify-content: center; background-color: #282828; }}
            .quiz-icon {{ width: 60%; height: auto; stroke: {highlight_color}; transition: stroke 0.2s ease-in-out; }}
            .album-art-link:hover .quiz-icon {{ stroke: {button_hover_color}; }}
            .control-arrow svg {{ width: {arrow_size}; height: {arrow_size}; stroke: {highlight_color}; stroke-width: {arrow_thickness}; transition: transform 0.3s ease, stroke 0.3s ease; }}
            .control-arrow:hover svg {{ stroke: {button_hover_color}; transform: scale({arrow_hover_scale}); }}
            h1 {{ color: #FFFFFF; font-size: clamp(1.5rem, 6vw, 2.5rem); margin-bottom: 0.5rem; min-height: 1.2em; }}
            h2 {{ color: #B3B3B3; font-size: clamp(1rem, 3vw, 1.2rem); margin: 0.5rem 0 1.5rem; min-height: 1.2em; }}
            .year-question {{ color: {highlight_color}; font-size: clamp(1.1rem, 4vw, 1.4rem); font-weight: bold; margin-top: 2rem; margin-bottom: 1.5rem;}}
            .info-section {{ width: 100%; text-align: center; }}
            .info-box strong {{ color: #FFFFFF; }}
            .info-box h3 {{ color: #FFFFFF; margin-top: 1.5rem; margin-bottom: 0.5rem;}}
            .info-divider {{ margin: 2rem 0; border: 0; border-top: 1px solid #333; }}
            .button {{ padding: 12px 24px; background-color: {highlight_color}; color: white; text-decoration: none; border-radius: 50px; font-weight: bold; margin-top: 20px; display: inline-block; transition: background-color 0.3s, transform 0.3s ease; }}
            .button:hover {{ background-color: {button_hover_color}; transform: scale({button_hover_scale}); }}
            .prominent-year {{ font-size: clamp(3rem, 12vw, 4rem); font-weight: bold; color: {highlight_color}; margin: 1rem 0; }}
            .progress-svg-container {{ width: 80%; max-width: 350px; margin: 20px auto 0; }}
            .progress-interactive-area {{ width: 80%; margin: 0 auto; height: 14px; cursor: pointer; }}
            .progress-interactive-area svg {{ width: 100%; height: 100%; overflow: visible; }}
            #progressTrack, #progressFill {{ fill: none; stroke-width: {progress_bar_thickness}; stroke-linecap: round; stroke-linejoin: round; transition: stroke-width 0.2s ease, stroke 0.2s ease; }}
            #progressTrack {{ stroke: #444; }}
            #progressFill {{ stroke: {highlight_color}; }}
            .progress-interactive-area:hover #progressFill, .progress-interactive-area:hover #progressTrack {{ stroke-width: {progress_bar_thickness + progress_bar_hover_increase_px}; }}
            .progress-interactive-area:hover #progressFill {{ stroke: {button_hover_color}; }}
            .player-mode-toggle {{ margin-top: 30px; margin-bottom: 35px; display: flex; flex-direction: column; align-items: center; gap: 10px; }}
            .toggle-label {{ font-size: 0.9rem; color: #B3B3B3; }}
            .switch {{ position: relative; display: inline-block; width: 50px; height: 28px; }}
            .switch input {{ opacity: 0; width: 0; height: 0; }}
            .slider {{ position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #444; transition: .4s; border-radius: 28px; }}
            .slider:before {{ position: absolute; content: ""; height: 22px; width: 22px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }}
            input:checked + .slider {{ background-color: {highlight_color}; }}
            input:checked + .slider:before {{ transform: translateX(22px); }}
        </style>
        </head><body><div class="container">
            <div class="album-art-container">
                <a href="/previous" class="control-arrow"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg></a>
                <a href="/play_pause" class="album-art-link">{image_html}</a>
                <a href="/next" class="control-arrow"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg></a>
            </div>
            <div class="progress-svg-container"><div class="progress-interactive-area"><svg viewBox="0 0 300 14"><path id="progressTrack" d=""></path><path id="progressFill" d=""></path></svg></div></div>
            <h1>{display_title}</h1><h2>{display_artist}</h2>{year_question_html}{info_section_html}
            <a href="{button_link}" class="button">{button_text}</a>
            <div class="player-mode-toggle"><label for="playerMode" class="toggle-label">Player-Modus</label><label class="switch"><input type="checkbox" id="playerMode" name="playerMode" {player_mode_checked}><span class="slider"></span></label></div>
            <a href="/logout" style="font-size: 0.8rem; color: #888;">Logout</a>
        </div>
        
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                const progressTrack = document.getElementById('progressTrack'); const progressFill = document.getElementById('progressFill'); const interactiveArea = document.querySelector('.progress-interactive-area'); const svgWidth = 300; const svgHeight = 14; const midHeight = svgHeight / 2; const amplitude = 6; const frequency = 0.05; const segments = 150; const waveSpeed = {wave_animation_speed};
                let initialTrackId = '{current_track_id}'; const pollingInterval = {polling_interval_seconds} * 1000;
                if (initialTrackId === 'None') {{ initialTrackId = null; }}
                let currentProgress = {progress_ms}; const totalDuration = {duration_ms}; const isPlaying = {str(is_playing).lower()};
                let animationFrameId = null; let animationStartTime = performance.now();
                function generateWavePath(phase) {{ let path = `M 0 ${{midHeight}}`; for (let i = 0; i <= segments; i++) {{ const x = (i / segments) * svgWidth; const fadeWidth = svgWidth * 0.1; let currentAmplitude = amplitude; if (x < fadeWidth) {{ currentAmplitude = amplitude * Math.sin((x / fadeWidth) * (Math.PI / 2)); }} else if (x > svgWidth - fadeWidth) {{ currentAmplitude = amplitude * Math.sin(((svgWidth - x) / fadeWidth) * (Math.PI / 2)); }} const y = midHeight + Math.sin(x * frequency + phase) * currentAmplitude; path += ` L ${{x.toFixed(3)}} ${{y.toFixed(3)}}`; }} return path; }}
                function updateProgressBar(progress) {{ if (totalDuration > 0) {{ const progressRatio = Math.min(progress / totalDuration, 1); const dynamicPhase = progressRatio * Math.PI * waveSpeed; const wavePath = generateWavePath(dynamicPhase); progressTrack.setAttribute('d', wavePath); progressFill.setAttribute('d', wavePath); const totalLength = progressFill.getTotalLength(); if (totalLength > 0) {{ progressFill.style.strokeDasharray = totalLength; progressFill.style.strokeDashoffset = totalLength * (1 - progressRatio); }} }} }}
                function animate(currentTime) {{ const elapsedTime = currentTime - animationStartTime; const newProgress = currentProgress + elapsedTime; updateProgressBar(newProgress); if (newProgress < totalDuration) {{ animationFrameId = requestAnimationFrame(animate); }} }}
                function startAnimation() {{ if (isPlaying) {{ animationStartTime = performance.now(); animationFrameId = requestAnimationFrame(animate); }} }}
                function stopAnimation() {{ if (animationFrameId) {{ cancelAnimationFrame(animationFrameId); animationFrameId = null; }} }}
                updateProgressBar(currentProgress); startAnimation();
                interactiveArea.addEventListener('click', function(event) {{ if (totalDuration > 0) {{ stopAnimation(); const rect = interactiveArea.getBoundingClientRect(); const clickX = event.clientX - rect.left; const clickPercentage = Math.max(0, Math.min(1, clickX / rect.width)); const seekPositionMs = Math.round(clickPercentage * totalDuration); currentProgress = seekPositionMs; updateProgressBar(currentProgress); startAnimation(); fetch('/seek', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ position_ms: seekPositionMs }}) }}).catch(error => console.error('Error seeking track:', error)); }} }});
                setInterval(function() {{ fetch('/check-song').then(response => response.ok ? response.json() : Promise.reject('Network response was not ok')).then(data => {{ if (data && data.track_id !== initialTrackId) {{ window.location.reload(); }} }}).catch(error => console.error('Error during polling:', error)); }}, pollingInterval);
                const playerModeToggle = document.getElementById('playerMode');
                if (playerModeToggle) {{ playerModeToggle.addEventListener('change', function() {{ const isEnabled = this.checked; fetch('/toggle-player-mode', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ playerMode: isEnabled }}) }}).then(response => response.ok ? response.json() : Promise.reject('Failed to toggle mode')).then(data => {{ if (data.success) {{ window.location.reload(); }} }}).catch(error => console.error('Error:', error)); }}); }}
            }});
        </script></body></html>"""
        
        return render_template_string(html_content)

    except Exception as e:
        # Die gestaltete Fehlerseite bleibt unverändert
        session.pop('quiz_state', None)
        session.pop('player_mode', None)
        error_html = f"""<!DOCTYPE html><html lang="de"><head><meta charset="UTF-8"><title>Fehler</title><style>body{{font-family:-apple-system,sans-serif;background-color:#121212;color:#b3b3b3;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center;padding:1rem}}.container{{width:calc(100% - 2rem);max-width:600px;padding:2.5rem;border-radius:12px;background-color:#1a1a1a;box-shadow:0 4px 15px rgba(0,0,0,0.5)}}h1{{color:#fff;margin-bottom:1rem}}p{{margin:1rem 0;line-height:1.6}}.button{{padding:12px 24px;background-color:{highlight_color};color:#fff;text-decoration:none;border-radius:50px;font-weight:700;margin-top:20px;display:inline-block;transition:background-color .3s,transform .3s ease}}.button:hover{{background-color:{button_hover_color};transform:scale(1.05)}}.error-details{{margin-top:2rem;font-size:.8rem;color:#666}}</style></head><body><div class="container"><h1>Fehler oder kein Song aktiv</h1><p>Möglicherweise wird gerade ein lokaler Song abgespielt, oder es ist kein Titel aktiv. Bitte stelle sicher, dass ein Song von Spotify wiedergegeben wird.</p><a href="/" class="button">Aktualisieren / Neu anmelden</a><p class="error-details"><small>Details: {e}</small></p></div></body></html>"""
        return render_template_string(error_html)


# Die restlichen Routen müssen jetzt auch den Spotify-Client über die Helfer-Funktion holen
@app.route("/check-song")
def check_song():
    sp = get_spotify_client()
    if not sp: return jsonify({'track_id': None})
    try:
        current_track = sp.currently_playing()
        track_id = current_track['item']['id'] if current_track and current_track.get('item') else None
        return jsonify({'track_id': track_id})
    except Exception:
        return jsonify({'track_id': None})

@app.route('/seek', methods=['POST'])
def seek():
    sp = get_spotify_client()
    if not sp: return jsonify({'success': False, 'error': 'Not logged in'})
    try:
        data = request.get_json()
        position_ms = data.get('position_ms')
        if isinstance(position_ms, int):
            sp.seek_track(position_ms)
            time.sleep(0.2)
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Invalid position'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/toggle-player-mode', methods=['POST'])
def toggle_player_mode():
    try:
        data = request.get_json()
        session['player_mode'] = data.get('playerMode', False)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route("/solve")
def solve():
    if 'quiz_state' in session:
        quiz_state = session['quiz_state']
        quiz_state['is_solved'] = True
        session['quiz_state'] = quiz_state
    return redirect(url_for('home'))

@app.route("/play_pause")
def play_pause():
    sp = get_spotify_client()
    if not sp: return redirect(url_for('home'))
    try:
        current_track = sp.currently_playing()
        if current_track and current_track['is_playing']:
            sp.pause_playback()
        else:
            sp.start_playback()
        time.sleep(0.5)
    except Exception:
        pass
    return redirect(url_for('home'))

@app.route("/next")
def next_track():
    sp = get_spotify_client()
    if not sp: return redirect(url_for('home'))
    try:
        sp.next_track()
        session.pop('quiz_state', None)
        time.sleep(0.5)
    except Exception:
        pass
    return redirect(url_for('home'))

@app.route("/previous")
def previous_track():
    sp = get_spotify_client()
    if not sp: return redirect(url_for('home'))
    try:
        sp.previous_track()
        session.pop('quiz_state', None)
        time.sleep(0.5)
    except Exception:
        pass
    return redirect(url_for('home'))


if __name__ == "__main__":

    app.run(host='0.0.0.0', debug=True)



