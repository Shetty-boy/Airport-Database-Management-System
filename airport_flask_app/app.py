from flask import Flask, render_template, request, redirect, url_for, flash
import oracledb
import config
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_very_secret_key_987'  # for flashing messages

def get_connection():
    return oracledb.connect(
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        dsn=config.DB_DSN
    )

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_passenger', methods=['GET', 'POST'])
def add_passenger():
    if request.method == 'POST':
        PassengerID = request.form['PassengerID']
        P_Name = request.form['P_Name']
        P_Contact = request.form['P_Contact']
        PassportID = request.form['PassportID']
        FlightID = request.form['FlightID']

        conn = get_connection()
        cursor = conn.cursor()

        # Check if PassengerID already exists
        cursor.execute("SELECT COUNT(*) FROM Passenger WHERE PassengerID = :1", (PassengerID,))
        (count,) = cursor.fetchone()

        if count > 0:
            flash('Passenger with this ID already exists. Please verify using your Passport ID.', 'info')
            cursor.close()
            conn.close()
            return render_template('verify_form.html')

        # Insert new passenger
        cursor.execute("""
            INSERT INTO Passenger (PassengerID, P_Name, P_Contact, PassportID, FlightID)
            VALUES (:1, :2, :3, :4, :5)
        """, (PassengerID, P_Name, P_Contact, PassportID, FlightID))
        conn.commit()

        cursor.close()
        conn.close()

        flash('Passenger added successfully. Please verify to continue.', 'success')
        return render_template('verify_form.html')

    return render_template('passenger_form.html')

@app.route('/passenger_info', methods=['POST'])
def passenger_info():
    PassengerID = request.form['PassengerID']
    PassportID = request.form['PassportID']

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM Passenger WHERE PassengerID = :1", (PassengerID,))
    passenger = cursor.fetchone()

    if not passenger or passenger[3] != PassportID:
        flash('Verification failed. Please enter valid Passenger ID and Passport ID.', 'danger')
        cursor.close()
        conn.close()
        return render_template('verify_form.html')

    # Get ticket details
    cursor.execute("""
        SELECT TicketID, TicketType, Price, PurchaseDate
        FROM Ticket
        WHERE PassengerID = :pid
    """, {'pid': PassengerID})
    ticket = cursor.fetchone()

    # Get flight details
    cursor.execute("""
        SELECT f.FlightID, f.DepartureTime, f.ArrivalTime,
               (f.ArrivalTime - f.DepartureTime) AS Duration,
               a.A_Name AS AirportName,
               al.AirlineName AS AirlineName
        FROM Flight f
        JOIN Airport a ON f.AirportID = a.AirportID
        JOIN Airline al ON f.AirlineID = al.AirlineID
        JOIN Passenger p ON f.FlightID = p.FlightID
        WHERE p.PassengerID = :pid
    """, {'pid': PassengerID})
    flight = cursor.fetchone()

    cursor.execute("""
        SELECT LuggageID, Lugg_Type, Lugg_Weight
        FROM Luggage
        WHERE PassengerID = :pid
    """, {'pid': PassengerID})
    luggage = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('passenger_info.html',
                           passenger=passenger,
                           ticket=ticket,
                           flight=flight,
                           luggage=luggage)


@app.route('/flight_details', methods=['GET', 'POST'])
def flight_details():
    if request.method == 'POST':
        airline_id = request.form['AirlineID']
        airline_pass = request.form['Airlinepass']
        flight_id = request.form['FlightID']

        conn = get_connection()
        cursor = conn.cursor()

        # Check airline credentials
        cursor.execute("SELECT * FROM Airline WHERE AirlineID = :1", (airline_id,))
        airline = cursor.fetchone()



        if not airline or airline[3] != airline_pass:
            flash('Verification failed. Please enter valid airline ID and Passport ID.', 'danger')
            cursor.close()
            conn.close()
            return render_template('flight_form.html')

        # Flight info
        cursor.execute("""
            SELECT FlightID, DepartureTime, ArrivalTime, AirlineID, FuelingStationID, AirportID
            FROM Flight
            WHERE FlightID = :fid AND AirlineID = :aid
        """, {'fid': flight_id, 'aid': airline_id})
        flight = cursor.fetchone()

        # Pilot info
        cursor.execute("""
            SELECT PilotID, Name, HoursExperience, LicenseNo
            FROM Pilot
            WHERE FlightID = :fid
        """, {'fid': flight_id})
        pilot = cursor.fetchall()

        # Fueling station info
        cursor.execute("""
            SELECT fs.FuelingStationID, fs.FS_Name, fs.Capacity, fs.AircraftsAttended, fs.FuelType
            FROM FuelingStation fs
            JOIN Flight f ON f.FuelingStationID = fs.FuelingStationID
            WHERE f.FlightID = :fid
        """, {'fid': flight_id})
        fueling_station = cursor.fetchone()

        cursor.close()
        conn.close()

        return render_template('flight_details.html',
                               airline=airline,
                               flight=flight,
                               pilot=pilot,
                               fueling_station=fueling_station)

    return render_template('flight_form.html')

@app.route('/airport_details', methods=['GET', 'POST'])
def airport_details():
    if request.method == 'POST':
        airport_id = request.form['AirportID'].strip()
        airport_pass = request.form['Airportpass'].strip()

        conn = get_connection()
        cursor = conn.cursor()

        # Fetch airport row and verify password
        cursor.execute("""
            SELECT AirportID, A_Name, Location, AirportType, AirportPass
            FROM Airport
            WHERE AirportID = :aid
        """, {'aid': airport_id})
        airport = cursor.fetchone()

        if not airport:
            flash('No Airport found with that ID.', 'warning')
            cursor.close()
            conn.close()
            return redirect(url_for('airport_details'))

        # Check if password matches
        stored_pass = airport[4].strip()  # Index 4 is AirportPass
        if stored_pass != airport_pass:
            flash('Authentication failed. Please enter correct Airport ID and Password.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('airport_details'))

        # Get Flights from this Airport
        cursor.execute("""
            SELECT FlightID, DepartureTime, ArrivalTime, AirlineID, FuelingStationID
            FROM Flight
            WHERE AirportID = :aid
        """, {'aid': airport_id})
        flights = cursor.fetchall()

        # Get Traffic Control Info
        cursor.execute("""
            SELECT TrafficControlID, TC_Name, TowerNo, TowerName
            FROM TrafficControl
            WHERE AirportID = :aid
        """, {'aid': airport_id})
        traffic_controls = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('airport_details.html',
                               airport=airport,
                               flights=flights,
                               traffic_controls=traffic_controls)

    return render_template('airport_form.html')
@app.route('/security_info', methods=['GET', 'POST'])
def security_info():
    if request.method == 'POST':
        passenger_id = request.form['PassengerID'].strip()
        passport_id = request.form['PassportID'].strip()

        conn = get_connection()
        cursor = conn.cursor()

        # Get Passenger Info and verify PassportID
        cursor.execute("""
            SELECT PassengerID, P_Name, P_Contact, PassportID, FlightID
            FROM Passenger
            WHERE PassengerID = :pid
        """, {'pid': passenger_id})
        passenger = cursor.fetchone()

        if not passenger:
            flash('Passenger not found with this ID.', 'warning')
            cursor.close()
            conn.close()
            return redirect(url_for('security_info'))

        stored_passport = passenger[3].strip()  # Assuming index 3 is PassportID
        if stored_passport != passport_id:
            flash('Passport ID does not match. Please try again.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('security_info'))

        # Get Security Info related to Passenger
        cursor.execute("""
            SELECT SecurityID, SecName, SecDept, AllocatedArea
            FROM Security
            WHERE PassengerID = :pid
        """, {'pid': passenger_id})
        security = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('security_details.html',
                               passenger=passenger,
                               security=security)

    return render_template('security_form.html')

if __name__ == 'main':
    app.run(debug=True)