import dash
from dash import Dash, dcc, html, Input, Output, State
import plotly.express as px
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import io

# Base URL of the Caddy server
BASE_URL = "https://data.ovh.pandonia-global-network.org/"

# Column names definition for the live data
# column_names = [
#     "Timestamp", "Fractional Days", "Effective Duration [s]", "Solar Zenith [deg]",
#     "Solar Azimuth [deg]", "Lunar Zenith [deg]", "Lunar Azimuth [deg]", "Fitting Residual RMS",
#     "Normalized RMS", "Expected RMS", "Expected Normalized RMS", "Station Pressure [mbar]",
#     "Processing Type Index", "Calibration File Version", "Calibration Validity Start",
#     "Mean Measured Value", "Effective Temp [°C]", "Residual Stray Light [%]",
#     "Wavelength Shift [nm]", "Total Wavelength Shift [nm]", "Resolution Change [%]",
#     "Integration Time [ms]", "Bright Cycles", "Filterwheel Position #1",
#     "Filterwheel Position #2", "Atmospheric Variability [%]", "Aerosol Optical Depth Start",
#     "Aerosol Optical Depth Center", "Aerosol Optical Depth End", "L1 Quality Flag",
#     "L1 Data Quality Sum DQ1", "L1 Data Quality Sum DQ2", "L2 Fit Quality Flag",
#     "L2 Fit Quality Sum DQ1", "L2 Fit Quality Sum DQ2", "L2 Ozone Quality Flag",
#     "L2 Ozone Quality Sum DQ1", "L2 Ozone Quality Sum DQ2", "Ozone Vertical Column [mol/m^2]",
#     "Ozone Uncertainty [mol/m^2]", "Ozone Structured Uncertainty [mol/m^2]",
#     "Ozone Common Uncertainty [mol/m^2]", "Ozone Total Uncertainty [mol/m^2]",
#     "Ozone RMS-based Uncertainty [mol/m^2]", "Ozone Effective Temp [K]",
#     "Effective Temp Uncertainty [K]", "Structured Temp Uncertainty [K]",
#     "Common Temp Uncertainty [K]", "Total Temp Uncertainty [K]",
#     "Direct Air Mass Factor", "Air Mass Factor Uncertainty", "Diffuse Correction [%]",
#     "Climatological NO2 Stratospheric Column [mol/m^2]",
#     "Uncertainty of Climatological NO2 Stratospheric Column [mol/m^2]"
# ]

# Function to list folders/files in a directory
def list_items(base_url):
    try:
        response = requests.get(base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        items = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.startswith("./") and not href.startswith(("../", "../../", "javascript", "operationfiles")):
                items.append(href.lstrip("./").rstrip("/"))  # Clean up the href
        return items
    except Exception as e:
        print(f"Error listing items: {e}")
        return []

# Initialize Dash app
app = Dash(__name__)
server = app.server
app.title = "Data Dashboard"

# Fetch initial list of locations
locations = list_items(BASE_URL)

# App layout
app.layout = html.Div([
    html.H1("Data Dashboard", style={"textAlign": "center"}),

    html.Div([
        html.Label("Select Location:"),
        dcc.Dropdown(
            id="location-dropdown",
            options=[{"label": loc, "value": loc} for loc in locations],
            placeholder="Choose a location",
        ),
    ], style={"width": "40%", "margin": "10px auto"}),

    html.Div([
        html.Label("Select Device:"),
        dcc.Dropdown(
            id="device-dropdown",
            placeholder="Choose a device",
        ),
    ], style={"width": "40%", "margin": "10px auto"}),

    html.Div([
        html.Label("Select File:"),
        dcc.Dropdown(
            id="file-dropdown",
            placeholder="Choose a file in L2 folder",
        ),
    ], style={"width": "40%", "margin": "10px auto"}),

    html.Div(id="output-content", style={"margin": "20px auto", "textAlign": "center"}),

    html.Div([
        html.Label("Filter by Date Range"),
        dcc.DatePickerRange(id="date-picker-range"),
    ], style={"width": "40%", "margin": "10px auto", "textAlign": "center"}),

    html.Div([
        html.Label("Select Column for Line Chart 1"),
        dcc.Dropdown(id="line-chart-column-dropdown1"),
    ], style={"width": "40%", "margin": "10px auto"}),

    dcc.Graph(id="line-chart1"),
    html.Div([
        html.Label("Select Column for Line Chart 2"),
        dcc.Dropdown(id="line-chart-column-dropdown2"),
    ], style={"width": "40%", "margin": "10px auto"}),
    dcc.Graph(id="line-chart2"),
])

# Callback to update the device dropdown based on selected location
@app.callback(
    Output("device-dropdown", "options"),
    Input("location-dropdown", "value")
)
def update_device_dropdown(selected_location):
    if selected_location:
        location_url = urljoin(BASE_URL, selected_location + "/")
        devices = list_items(location_url)
        return [{"label": device, "value": device} for device in devices]
    return []

# Callback to update the file dropdown based on selected device
@app.callback(
    Output("file-dropdown", "options"),
    [Input("location-dropdown", "value"),
     Input("device-dropdown", "value")]
)
def update_file_dropdown(selected_location, selected_device):
    if selected_location and selected_device:
        l2_url = urljoin(BASE_URL, f"{selected_location}/{selected_device}/L2/")
        files = list_items(l2_url)
        return [{"label": file, "value": urljoin(l2_url, file)} for file in files]
    return []


def extract_column_names(file_content):
    """
    Extract column names from the provided file content, ensuring unique names.
    """
    column_names = []
    seen_names = {}
    for line in file_content:
        if line.strip().startswith("Column") and not line.strip().startswith("From"):
            # Extract column name from description (e.g., "Column 1: UT date and time")
            parts = line.split(":", 1)
            if len(parts) > 1:
                base_name = parts[1].strip().split(",")[0]  # Take text before the comma
                # Make the name unique
                if base_name in seen_names:
                    seen_names[base_name] += 1
                    unique_name = f"{base_name}_{seen_names[base_name]}"
                else:
                    seen_names[base_name] = 0
                    unique_name = base_name
                column_names.append(unique_name)
    return column_names


timestamp_column = None  # Global variable to store the timestamp column name

@app.callback(
    [
        Output("line-chart-column-dropdown1", "options"),
        Output("line-chart-column-dropdown2", "options"),
        Output("output-content", "children"),
    ],
    Input("file-dropdown", "value")
)
def process_selected_file(file_url):
    global uploaded_df, timestamp_column

    if file_url:
        try:
            response = requests.get(file_url)
            response.raise_for_status()
            data = response.content.decode("utf-8", errors="ignore").splitlines()

            # Detect column names section
            column_names = extract_column_names(data)

            # Detect the data section
            for i, line in enumerate(data):
                if line.strip().startswith("202"):  # Detect data rows (starting with a timestamp)
                    data_section = "\n".join(data[i:])
                    break
            else:
                return [], [], "No valid data found in the file."

            # Count the number of fields in the first data row
            sample_row = data_section.splitlines()[0]
            actual_field_count = len(sample_row.split())

            # Adjust column names to match the actual field count
            if len(column_names) < actual_field_count:
                column_names.extend([f"Unnamed_{i}" for i in range(len(column_names), actual_field_count)])

            # Create DataFrame
            df = pd.read_csv(
                io.StringIO(data_section),
                delim_whitespace=True,
                names=column_names,
                on_bad_lines="skip",  # Skip problematic lines
            )

            # Dynamically identify the timestamp column
            possible_timestamp_columns = ["Timestamp", "UT date and time for measurement center"]
            timestamp_column = next((col for col in column_names if col in possible_timestamp_columns), None)
            if not timestamp_column:
                return [], [], "No valid timestamp column found in the file."

            # Convert timestamp column to datetime
            df[timestamp_column] = pd.to_datetime(df[timestamp_column], format="%Y%m%dT%H%M%S.%fZ", errors="coerce")
            df.drop_duplicates(subset=[timestamp_column], inplace=True)
            df.sort_values(by=timestamp_column, inplace=True)

            # Store DataFrame globally for chart callbacks
            uploaded_df = df

            numeric_columns = [{"label": col, "value": col} for col in column_names if col != timestamp_column]
            return numeric_columns, numeric_columns, f"Loaded file: {file_url}"
        except Exception as e:
            return [], [], f"Error loading file: {e}"
    return [], [], "No file selected."




@app.callback(
    [Output("line-chart1", "figure"), Output("line-chart2", "figure")],
    [
        Input("line-chart-column-dropdown1", "value"),
        Input("line-chart-column-dropdown2", "value"),
        Input("date-picker-range", "start_date"),
        Input("date-picker-range", "end_date"),
    ],
)
def update_charts(column1, column2, start_date, end_date):
    global uploaded_df, timestamp_column

    # Check if uploaded_df is initialized
    if uploaded_df.empty or not timestamp_column:
        return px.line(title="No Data Available"), px.line(title="No Data Available")

    df = uploaded_df.copy()

    # Filter by date range if specified
    if start_date and end_date:
        df = df[(df[timestamp_column] >= pd.to_datetime(start_date)) & (df[timestamp_column] <= pd.to_datetime(end_date))]

    # Create the first chart
    if column1:
        fig1 = px.line(df, x=timestamp_column, y=column1, title=f"Chart 1: {column1} Over Time")
    else:
        fig1 = px.line(title="No Data Available")

    # Create the second chart
    if column2:
        fig2 = px.line(df, x=timestamp_column, y=column2, title=f"Chart 2: {column2} Over Time")
    else:
        fig2 = px.line(title="No Data Available")

    return fig1, fig2



if __name__ == "__main__":
    uploaded_df = pd.DataFrame()  # Initialize an empty DataFrame for global use
    app.run_server(debug=True)
