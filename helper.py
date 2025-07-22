import urllib  
import json 
import pandas as pd  
import folium  
import datetime as dt  
from geopy.distance import geodesic  
from geopy.geocoders import Nominatim  
import streamlit as st 
from streamlit_folium import folium_static


@st.cache_data  

# Define the function to query station status from a given URL
def query_station_status(url):
    with urllib.request.urlopen(url) as data_url:  
        data = json.loads(data_url.read().decode())  
    # Data Preproccessing
    df = pd.DataFrame(data['data']['stations'])  
    df = df[df.is_renting == 1]  
    df = df[df.is_returning == 1]  
    df = df.drop_duplicates(['station_id', 'last_reported']) 
    df.last_reported = df.last_reported.map(lambda x: dt.datetime.utcfromtimestamp(x)) 
    df['time'] = data['last_updated']  
    df.time = df.time.map(lambda x: dt.datetime.utcfromtimestamp(x))  
    df = df.set_index('time')  
    df.index = df.index.tz_localize('UTC')  
    df = pd.concat([df, df['num_bikes_available_types'].apply(pd.Series)], axis=1)  
    return df  

# Define the function to get station latitude and longitude from a given URL
def get_station_latlon(url):
    with urllib.request.urlopen(url) as data_url:  
        latlon = json.loads(data_url.read().decode())  
    latlon = pd.DataFrame(latlon['data']['stations'])  
    return latlon  

# Define the function to join two DataFrames on station_id
def join_latlon(df1, df2):
    df = df1.merge(df2[['station_id', 'lat', 'lon']], 
                how='left', 
                on='station_id')  
    return df  

# Function to determine marker color based on the number of bikes available
def get_marker_color(num_bikes_available):
    if num_bikes_available > 3:
        return 'green'
    elif 0 < num_bikes_available <= 3:
        return 'yellow'
    else:
        return 'red'

# Define the function to geocode an address
def geocode(address):
    geolocator = Nominatim(user_agent="clicked-demo")  
    location = geolocator.geocode(address) 
    if location is None:
        return ''  
    else:
        return (location.latitude, location.longitude)  

# Define the function to get bike availability near a location
def get_bike_availability(latlon, df, input_bike_modes):
    """Calculate distance from each station to the user and return a single station id, lat, lon"""
    if len(input_bike_modes) == 0 or len(input_bike_modes) == 2:  # If no mode selected, assume both bikes are selected
        i = 0
        df['distance'] = ''
        while i < len(df):
            df.loc[i, 'distance'] = geodesic(latlon, (df['lat'][i], df['lon'][i])).km  
            i = i + 1
        df = df.loc[(df['ebike'] > 0) | (df['mechanical'] > 0)] 
        chosen_station = []
        chosen_station.append(df[df['distance'] == min(df['distance'])]['station_id'].iloc[0]) 
        chosen_station.append(df[df['distance'] == min(df['distance'])]['lat'].iloc[0])
        chosen_station.append(df[df['distance'] == min(df['distance'])]['lon'].iloc[0])
    else:
        i = 0
        df['distance'] = ''
        while i < len(df):
            df.loc[i, 'distance'] = geodesic(latlon, (df['lat'][i], df['lon'][i])).km  # Calculate distance to each station
            i = i + 1
        df = df.loc[df[input_bike_modes[0]] > 0]  
        chosen_station = []
        chosen_station.append(df[df['distance'] == min(df['distance'])]['station_id'].iloc[0])  
        chosen_station.append(df[df['distance'] == min(df['distance'])]['lat'].iloc[0])
        chosen_station.append(df[df['distance'] == min(df['distance'])]['lon'].iloc[0])
    return chosen_station  # Return the chosen station

# Define the function to get dock availability near a location
def get_dock_availability(latlon, df):
    """Calculate distance from each station to the user and return a single station id, lat, lon"""
    i = 0
    df['distance'] = ''
    while i < len(df):
        df.loc[i, 'distance'] = geodesic(latlon, (df['lat'][i], df['lon'][i])).km  
        i = i + 1
    df = df.loc[df['num_docks_available'] > 0]  
    chosen_station = []
    chosen_station.append(df[df['distance'] == min(df['distance'])]['station_id'].iloc[0])  
    chosen_station.append(df[df['distance'] == min(df['distance'])]['lat'].iloc[0])
    chosen_station.append(df[df['distance'] == min(df['distance'])]['lon'].iloc[0])
    return chosen_station  # Return the chosen station

import requests  # Import requests for making HTTP requests

# Define the function to run OSRM and get route coordinates and duration
def run_osrm(chosen_station, iamhere):
    start = "{},{}".format(iamhere[1], iamhere[0])  
    end = "{},{}".format(chosen_station[2], chosen_station[1])  
    url = 'http://router.project-osrm.org/route/v1/driving/{};{}?geometries=geojson'.format(start, end)  # Create the OSRM API URL

    headers = {'Content-type': 'application/json'}
    r = requests.get(url, headers=headers)  
    print("Calling API ...:", r.status_code)  

    routejson = r.json()  # Parse the JSON response
    coordinates = []
    i = 0
    lst = routejson['routes'][0]['geometry']['coordinates']
    while i < len(lst):
        coordinates.append([lst[i][1], lst[i][0]]) 
        i = i + 1
    duration = round(routejson['routes'][0]['duration'] / 60, 1)  

    return coordinates, duration  