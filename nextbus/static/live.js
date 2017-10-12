const INTERVAL = 60;
const REFRESH = false;

function LiveData(atcoCode, postURL, tableElement, countdownElement) {
    var self = this;
    this.atcoCode = atcoCode;
    this.postURL = postURL;
    this.table = tableElement;
    this.cd = countdownElement;
    this.getData = _getData;
    this.printData = _printData;
    this.initialise = _initialise;
    
    function _getData() {
        console.log(`Sending POST request to ${self.postURL} with code='${self.atcoCode}'`);
        $.ajax({
            type: "POST",
            contentType: "application/json; charset=utf-8",
            url: self.postURL,
            data: JSON.stringify({code: self.atcoCode}),
            success: self.printData,
            dataType: "json"
        });
    }

    function _printData(data, status) {
        console.log(`Request for stop '${self.atcoCode}': ${status}`);
        var expDate;
        var reqDate = new Date(data.request_time);
        var strTable = "<p>Live bus times as of " + printDate(reqDate) + ":</p>"
        strTable += '<table id="servicesTable">\
            <tr><th>Bus</th><th>Destination</th><th>Expected</th><th></th>\
            <th>Operator</th></tr>';
        if (data.departures.all) {
            for (s of data.departures.all) {
                if (s.expected_departure_date || s.expected_departure_time) {
                    live = true;
                    expDate = new Date(
                        s.expected_departure_date + ' '
                        + s.expected_departure_time
                    );
                } else {
                    live = false;
                    expDate = new Date(s.date + ' ' + s.aimed_departure_time);
                }
                var dueMins = Math.round((expDate - reqDate) / 60000);
                var strDue = (dueMins < 2) ? "Due" : (dueMins + " mins");
                if (dueMins > 60)
                    break;
                strTable += (
                    `<tr><td>${s.line}</td><td>${s.direction}</td>`
                    + `<td>${strDue}</td><td>${(live) ? 'Live' : ''}</td>`
                    + `<td>${s.operator_name}</td></tr>`
                );
            }
            strTable += '</table>';
            self.table.innerHTML = strTable;
            console.log(
                "Created table with " + data.departures.all.length
                + " services for stop '" + self.atcoCode + "'."
            );
        } else {
            self.table.innerHTML = "<p>No buses expected.</p>";
            console.log(`No services found for stop ${self.atcoCode}.`);
        }
    }

    function _initialise() {
        self.getData();
        if (REFRESH) {
            var time = INTERVAL;
            window.setInterval(function() {
                if (--time > 0) {
                    var s = (time != 1) ? 's' : ''
                    self.cd.innerHTML = `Refreshing in ${time} second${s}...`
                } else {
                    self.cd.innerHTML = 'Refreshing now...';
                }
                if (time <= 0) {
                    self.getData();
                    time = INTERVAL;
                }
            }, 1000);
        } else {
            self.cd.innerHTML = '';
        }
    }
}

function printDate(dateObj) {
    var dayNames = [
        'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
        'Saturday'
    ];
    var monthNames = [
        'January', 'February', 'March', 'April', 'May', 'June', 'July',
        'August', 'September', 'October', 'November', 'December'
    ];
    var date = (
        dateObj.getHours() + ':'
        + dateObj.getMinutes() + ', '
        + dayNames[dateObj.getDay()] + ' '
        + dateObj.getDate() + ' '
        + monthNames[dateObj.getMonth()] + ' '
        + dateObj.getFullYear()
    );
    return date;
}