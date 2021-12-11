import json, random, uuid, sqlite3, time, logging, os, shutil
from flask import Flask, request, redirect, render_template, url_for, session, g
import requests
from urllib.parse import quote
from flask_session import Session

from utils import prime_user_from_access_token, prepare_playlists, prepare_data, execute_clustering, gather_cluster_size_from_submission, organize_cluster_data_for_display, refreshTheToken

# Authentication Steps, paramaters, and responses are defined at https://developer.spotify.com/web-api/authorization-guide/
# Visit this url to see all the steps, parameters, and expected response.

app = Flask(__name__)

handler = logging.StreamHandler()

app.logger.addHandler(handler)

random.seed(420)

DEBUG_MODE = False

if DEBUG_MODE:
    # Server-side Parameters
    CLIENT_SIDE_URL = "http://127.0.0.1"
    # PORT = 9000
    PORT = 8095
    REDIRECT_URI = "{}:{}/callback".format(CLIENT_SIDE_URL,PORT)
    SCHEME='http'
else:
    CLIENT_SIDE_URL = "https://radial-app.com"
    REDIRECT_URI = "{}/callback".format(CLIENT_SIDE_URL)
    SCHEME='https'


# app.config["SESSION_PERMANENT"] = False
# app.config['SESSION_TYPE'] = 'filesystem'
# app.secret_key = str(uuid.uuid4())
# Session(app)
DATABASE = 'app_data/basic_user_credentials.db'
DB_CREATION_SCRIPT = 'app_data/create_radial_tables.sql'
USER_DATA_PATH = 'app_data/user_data'
def get_db():
    db = sqlite3.connect(DATABASE)
    return db


def init_db():
    with app.app_context():
        if os.path.exists(DATABASE):
            os.remove(DATABASE)
        db = get_db()
        with app.open_resource(DB_CREATION_SCRIPT, mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()


init_db()


def close_connection(db):
    db.close()

#  Client Keys
CLIENT_ID = "7ec4038de1184e2fb0a1caf13352e295"
CLIENT_SECRET = '18fa59e0d4614c139f4c6102f5bc965a'

# Spotify URLS
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE_URL = "https://api.spotify.com"
API_VERSION = "v1"
SPOTIFY_API_URL = "{}/{}".format(SPOTIFY_API_BASE_URL, API_VERSION)



SCOPE = "user-read-recently-played user-top-read  playlist-modify-public playlist-modify-private user-library-modify playlist-read-private user-read-email user-read-private user-library-read playlist-read-collaborative"

auth_query_parameters = {
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPE,
    "client_id": CLIENT_ID,
    "show_dialog":'true'
}



@app.route("/")
def index():
    return render_template('homepage.html')

@app.route("/appeducation")
def appeducation():
    spotify_user_id = request.args.get('spotify_user_id')
    return render_template('appeducation.html', spotify_user_id = spotify_user_id)


@app.route("/authenticateuser")
def authenticateuser():
    # Auth Step 1: Authorization
    url_args = "&".join(["{}={}".format(key, quote(val)) for key, val in auth_query_parameters.items()])
    auth_url = "{}/?{}".format(SPOTIFY_AUTH_URL, url_args)
    return redirect(auth_url)


@app.route("/callback")
def callback():
    # Auth Step 4: Requests refresh and access tokens
    auth_token = request.args['code']
    code_payload = {
        "grant_type": "authorization_code",
        "code": str(auth_token),
        "redirect_uri": REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET

    }
    app.logger.info(msg=code_payload)
    post_request = requests.post(SPOTIFY_TOKEN_URL, data=code_payload)
    # Auth Step 5: Tokens are Returned to Application
    response_data = json.loads(post_request.text)
    app.logger.info(f"{response_data}")
    access_token = response_data["access_token"]
    refresh_token = response_data["refresh_token"]
    # token_type = response_data["token_type"]
    expires_in = response_data["expires_in"]

    # Auth Step 6: Use the access token to access Spotify API
    authorization_header = {"Authorization": "Bearer {}".format(access_token), 'Content-Type': 'application/x-www-form-urlencoded'}

    # Get profile data
    user_profile_api_endpoint = "{}/me".format(SPOTIFY_API_URL)
    profile_response = requests.get(user_profile_api_endpoint, headers=authorization_header)
    # app.logger.info(f"PROFILE RESPONSE {profile_response.text}")
    profile_data = json.loads(profile_response.text)
    user_id = profile_data['id']
    user_display_name = profile_data['display_name']


    #FUNCTION HERE TO ADD USER INFO TO TABLE IN DB
    db_connection = get_db()
    cursor = db_connection.cursor()
    all_data = cursor.execute("SELECT SpotifyID FROM RadialUsers;").fetchall()
    # app.logger.info(f"{all_data}")
    verify_prior_entry = (user_id,) in all_data
    app.logger.info(f"User already in DB: {verify_prior_entry} ({all_data})")
    if verify_prior_entry:
        user_data = cursor.execute(f'SELECT * FROM RadialUsers WHERE SpotifyID="{user_id}" ORDER BY AccessExpires DESC;').fetchone()
        recorded_expiration = user_data[-1] 
        # app.logger.info(f"RECORDED EXPIRATION: {recorded_expiration}")
        if time.time() > int(recorded_expiration):
            #refresh token
            refresh_token_data = refreshTheToken(refresh_token)
            access_token = refresh_token_data['accessToken']
            expires_in = refresh_token_data['expiresAt']

        replace_statement = f'UPDATE RadialUsers SET RefreshToken=?, AccessExpires=? WHERE SpotifyId="{user_id}";'
        replaceable_values = (refresh_token, expires_in + int(time.time()))
        # app.logger.info(f"updating with these values to db {replaceable_values}")
        cursor.execute(replace_statement, replaceable_values)
    
    else:
        app.logger.info('BRAND NEW USER ADDING TO DB')
        insert_statement = 'INSERT INTO RadialUsers(SpotifyId,DisplayName,AccessToken,RefreshToken,AccessExpires) VALUES(?,?,?,?,?);'
        insertable_values = (user_id,user_display_name,access_token, refresh_token, expires_in)
        cursor.execute(insert_statement, insertable_values)
    
    db_connection.commit()
    cursor.close()

    if user_id in os.listdir(f"{USER_DATA_PATH}"):
       shutil.rmtree(f"{USER_DATA_PATH}/{user_id}")

    os.mkdir(f"{USER_DATA_PATH}/{user_id}")

    app.logger.info(msg='Set user')


    #make user 
    # user = prime_user_from_access_token(user_id, access_token)
    # user.name = user_display_name
    # session['VALID_USER'] = user
    # return redirect(f"{CLIENT_SIDE_URL}/appeducation")
    # return render_template('appeducation.html', spotify_user_id = user_id)
    proper_url = url_for('appeducation', spotify_user_id = user_id, _scheme=SCHEME, _external=True)
    return redirect(proper_url)




@app.route('/clustertracks', methods=['POST'])
def clustertracks():
    # app.logger.info(f"{request.form}")
    # app.logger.info(f"{request.args}")
    spotify_user_id = request.args.get('spotify_user_id')
    algorithm = request.form.get('algorithm')
    desired_clusters = request.form.get('desired_clusters')
    chosen_algorithm = algorithm
    chosen_clusters = gather_cluster_size_from_submission(desired_clusters)
    # app.logger.info(msg='cluster size determined')
    # session['ALGORITHM_CHOSEN'] = chosen_algorithm
    # session['CLUSTERING_CHOSEN'] = chosen_clusters

    # app.logger.info(msg=f'algorithm: {chosen_algorithm}')
    # app.logger.info(msg=f'clusters: {chosen_clusters}')

    # app.logger.info(msg=f'SELECT DisplayName FROM RadialUsers WHERE SpotifyID="{spotify_user_id}";')
    retrieved_id, retrieved_display_name, retrieved_access_token = get_db().cursor().execute(f'SELECT * FROM RadialUsers WHERE SpotifyID="{spotify_user_id}";').fetchone()[:3]
    assert spotify_user_id == retrieved_id


    user_obj = prime_user_from_access_token(spotify_user_id, retrieved_access_token)
    # auth_header = {'Authorization': f'Bearer {retrieved_access_token}'}


    app.logger.info(f"gathered the following from the db: {retrieved_id} vs {spotify_user_id}, {retrieved_display_name}, {retrieved_access_token}")

    #gather data

    app.logger.info(msg='preparing data')
    user_prepared_data = prepare_data(user_obj)
    user_prepared_data.to_csv(f'app_data/user_data/{retrieved_id}/user_prepared_data.csv')

    app.logger.info(msg='data prepared')
    # app.logger.info(msg=user_prepared_data)



    labelled_data = execute_clustering(chosen_algorithm,chosen_clusters,user_prepared_data)
    labelled_data.to_csv(f'app_data/user_data/{retrieved_id}/labelled_data.csv')


    # session['LABELLED_DATA'] = labelled_data

    app.logger.info(msg='data clustered')

    prepared_playlists = prepare_playlists(user_obj,labelled_data)
    with open(f'app_data/user_data/{retrieved_id}/prepared_playlists.json','w') as writer:
        json.dump(prepared_playlists,writer)
    app.logger.info(msg='ready for upload')

    #FUNCTION HERE TO ADD USER INFO TO TABLE IN DB
    insert_statement = 'INSERT INTO Clusterings(ClusteringID,SpotifyID,ClusterAlgorithm,ClustersChosen) VALUES(?,?, ?, ?)'
    insertable_values = (str(uuid.uuid4()), retrieved_id, chosen_algorithm,chosen_clusters)
    db_connection = get_db()
    cursor = db_connection.cursor()
    cursor.execute(insert_statement, insertable_values)
    db_connection.commit()
    cursor.close()
    # close_connection()

    # session['PREPARED_PLAYLISTS'] = prepared_playlists   

    # session['DEPLOYED_CLUSTERS_OBJS'] = {}
    # Combine profile and playlist data to display
    # return render_template("clusteringresults.html", stringified_playlists = json.dumps(prepared_playlists))
    # return redirect(f"{CLIENT_SIDE_URL}/clusteringresults")
    return redirect(url_for('clusteringresults', spotify_user_id = retrieved_id, chosen_clusters = chosen_clusters, chosen_algorithm = chosen_algorithm, _scheme=SCHEME, _external=True))




# @app.route('/loading')
# def loading():
#     pass
#     # return render_template('loading-page.html')






@app.route("/clusteringresults")
def clusteringresults():
    app.logger.info(f"{request.args}")
    spotify_user_id = request.args.get('spotify_user_id')
    with open(f'{USER_DATA_PATH}/{spotify_user_id}/prepared_playlists.json') as reader:
        prepared_playlists = json.load(reader) 
    chosen_clusters = int(request.args.get('chosen_clusters'))
    chosen_algorithm = request.args.get('chosen_algorithm')

    # prepared_playlists = session['PREPARED_PLAYLISTS']
    retrieved_id, retrieved_display_name, retrieved_access_token = get_db().cursor().execute(f'SELECT * FROM RadialUsers WHERE SpotifyID="{spotify_user_id}"').fetchone()[:3]
    auth_header = {'Authorization': f'Bearer {retrieved_access_token}'}

    displayable_data, total_organized_playlist_data = organize_cluster_data_for_display(auth_header,prepared_playlists)

    with open(f'app_data/user_data/{retrieved_id}/total_organized_playlist_data.json','w') as writer:
        json.dump(total_organized_playlist_data,writer)

    # app.logger.info(f'deployed clusters already exist: {"DEPLOYED_CLUSTERS_OBJS" in session}')

    # if "DEPLOYED_CLUSTERS_OBJS" in session:
    #     app.logger.info(f"{session['DEPLOYED_CLUSTERS_OBJS']}")

    return render_template("clusteringresults.html", displayable_data = displayable_data, total_organized_playlist_data = total_organized_playlist_data, chosen_algorithm = chosen_algorithm, chosen_clusters = chosen_clusters, spotify_user_id = spotify_user_id)


@app.route("/clusteringresults#<cluster_id>")
def deploy_cluster(cluster_id):
    app.logger.info(f"cluster id passed: {cluster_id}")
    app.logger.info(f"get params: {request.args.keys()}")
    app.logger.info(f"get params values: {list(request.args.values())}")
    
    #weird ampsersand issues

    spotify_user_id = request.args.get('spotify_user_id')
    with open(f'{USER_DATA_PATH}/{spotify_user_id}/total_organized_playlist_data.json') as reader:
        total_organized_playlist_data = json.load(reader) 
    
    # total_organized_playlist_data = ast.literal_eval()
    chosen_algorithm = request.args.get('chosen_algorithm' if 'chosen_algorithm' in request.args else 'amp;chosen_algorithm')
    chosen_clusters = int(request.args.get('chosen_clusters' if 'chosen_clusters' in request.args else 'amp;chosen_clusters'))


    retrieved_id, retrieved_display_name, retrieved_access_token = get_db().cursor().execute(f'SELECT * FROM RadialUsers WHERE SpotifyID="{spotify_user_id}";').fetchone()[:3]

    app.logger.info(f"gathered the following from the db: {retrieved_id}, {retrieved_display_name}, {retrieved_access_token}")

    # auth_header = {'Authorization': f'Bearer {retrieved_access_token}'}

    specified_user = prime_user_from_access_token(retrieved_id, retrieved_access_token)
    specified_user.optional_display_id = retrieved_display_name


    # specified_user = session['VALID_USER']
    app.logger.info(f'{total_organized_playlist_data.keys()}')
    try:
        # tracks_to_add = session['PREPARED_PLAYLISTS'][int(cluster_id)]
        tracks_to_add = total_organized_playlist_data[int(cluster_id)]['all_tracks']
    
    except KeyError:
        tracks_to_add = total_organized_playlist_data[cluster_id]['all_tracks']
    
        
        
    # specified_algorithm = session['ALGORITHM_CHOSEN']
    specified_algorithm = chosen_algorithm
    # specified_clusters = session['CLUSTERING_CHOSEN']
    specified_clusters = chosen_clusters
    clustering_type = f"{specified_algorithm.title()} ({specified_clusters})"
    playlist_obj = specified_user.deploy_single_cluster_playlist(tracks_to_add, int(cluster_id) + 1, clustering_type)
    playlist_url = f'https://open.spotify.com/playlist/{playlist_obj.playlist_id}'

    #add description
    # playlist_obj.update_playlist_metadata(specified_user,{'description':playlist_obj.description})
    # return render_template("clusteringresults.html", displayable_data = displayable_data, total_organized_playlist_data = total_organized_playlist_data, chosen_algorithm = session['ALGORITHM_CHOSEN'], chosen_clusters = session['CLUSTERING_CHOSEN'])
    # if 'DEPLOYED_CLUSTERS_OBJS' in session:
    #     session['DEPLOYED_CLUSTERS_OBJS'][int(cluster_id)] = playlist_obj
    # else:
    #     session['DEPLOYED_CLUSTERS_OBJS'] = {int(cluster_id): playlist_obj}
    return redirect(playlist_url)
    




if __name__ == "__main__":
    if DEBUG_MODE:
        app.run(debug=True, port=PORT)
    else:
        app.run(host = '0.0.0.0')
        import sys; sys.exit(0)
