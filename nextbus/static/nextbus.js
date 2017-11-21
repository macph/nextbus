/*
Functions for list of stops.
*/

const INTERVAL = 60;
const REFRESH = true;
const TIME_LIMIT = 60;

/** Filters services in list
 * @constructor
 * @param {Object} callback - Function called to redraw list
 * @param {string} args - List of services to add at start
 */
function ServicesFilter(callback, ...args) {
    var self = this;
    this.callback = callback;
    this.services = args;
    this.filterList = [];

    /**
     * Adds a service to whitelist, refreshing table
     * @param {string} s - Service to add
     */
    this.add = function(s) {
        if (self.services.indexOf(s) > -1 && self.filterList.indexOf(s) == -1) {
            console.log(`Adding '${s}' to filtered list '[${self.filterList}]'.`);
            self.filterList.push(s);
            self.callback();
        } else if (self.filterList.indexOf(s) == -1) {
            console.log(`Service '${s}' is not in list of current services.`);
        } else {
            console.log(`Service '${s}' is already in filtered list.`);
        }
    }

    /**
     * Removes a service from whitelist, refreshing table
     * @param {string} s - Service to remove
     */
    this.del = function(s) {
        index = self.filterList.indexOf(s);
        if (index > -1) {
            console.log(`Deleting '${s}' from filtered list '[${self.filterList}]'.`);
            self.filterList.splice(index, 1);
            self.callback();
        } else {
            console.log(`Service '${s}' is not in filtered list.`);
        }
    }

    /**
     * Resets filter list, refreshing table
     */
    this.reset = function() {
        if (self.filterList.length > 0) {
            console.log(`Resetting filtered list ${self.filterList}.`);
            self.filterList.length = 0;
            self.callback();
        } else {
            console.log(`Filtered list is empty.`);
        }
    }

    /**
     * Checks if whitelist is active & service is not in list, therefore excluding
     * @param {string} s - Service to check
     */
    this.exclude = function(s) {
        return (self.filterList.length > 0 && self.filterList.indexOf(s) === -1);
    }

    /**
     * Checks if whitelist is inactive or service is in list, therefore including
     * @param {string} s - Service to check
     */
    this.include = function(s) {
        return (self.filterList.length === 0 || self.filterList.indexOf(s) > -1);
    }
}

/**
 * Retrieves live data and displays it in a table
 * @constructor
 * @param {string} atcoCode - ATCO code for stop
 * @param {string} postURL - URL to send requests to
 * @param {Element} tableElement - Table element in document
 * @param {Element} timeElement - Element in document showing time when data was retrieved
 * @param {Element} countdownElement - Element in document showing time before next refresh
 */
function LiveData(atcoCode, postURL, tableElement, timeElement, countdownElement) {
    var self = this;
    this.atcoCode = atcoCode;
    this.postURL = postURL;
    this.table = tableElement;
    this.hTime = timeElement;
    this.cd = countdownElement;
    this.data = null;
    this.isLive = true;
    
    this.getData = _getData;
    this.printData = _printData;
    this.updateData = _updateData;
    this.initialise = _initialise;
    this.filter = new ServicesFilter(_printData);

    /**
     * Get list of all services to pass on to filtering class
     */
    this.getAllServices = function() {
        var listServices = [];
        if (self.data.services.length > 0) {
            listServices = self.data.services.map(s => s.name);
        }
        return [...new Set(listServices)];
    }

    /**
     * Gets data from server, refreshing table
     */
    function _getData() {
        console.log(`Sending POST request to ${self.postURL} with code='${self.atcoCode}'`);
        var request = new XMLHttpRequest();
        request.open('POST', self.postURL, true);
        request.setRequestHeader('Content-Type', 'application/json; charset=utf-8');

        request.onreadystatechange = function() {
            if (request.readyState === XMLHttpRequest.DONE) {
                if (request.status === 200) {
                    console.log(`Request for stop '${self.atcoCode}' successful`);
                    self.data = JSON.parse(request.responseText);
                    self.filter.services = self.getAllServices();
                    self.isLive = true;
                    self.printData();
                } else if (self.data != null) {
                    self.isLive = false;
                    self.printData();
                } else {
                    self.isLive = false;
                    self.hTime.innerHTML = "No data available";
                }
            }
        }

        request.send(JSON.stringify({code: self.atcoCode}));
    }

    /**
     * Draws table from data
     */
    function _printData() {
        var clLive;
        if (self.isLive) {
            clLive = 'text-green';
        } else {
            self.updateData();
            clLive = 'text-red';
        }

        function strDue(sec) {
            let due = Math.round(sec / 60);
            let str = (due < 2) ? 'due' : due + ' min';
            return str;
        }

        if (self.data.services.length > 0) {
            console.log(`Found ${self.data.services.length} services for stop '${self.atcoCode}'.`);
            self.hTime.innerHTML = ((self.isLive) ? 'Live times at ' : 'Estimated times from ') + self.data.local_time;

            var table = document.createElement('div');
            table.className = 'list-services';
            for (s of self.data.services) {
                if (self.filter.exclude(s.name)) {
                    continue;
                }
                let row = document.createElement('a');
                row.className = 'row-service';

                let cellNumber = document.createElement('div');
                cellNumber.className = 'item-service-num';
                cellNumber.appendChild(document.createTextNode(s.name));

                let cellDest = document.createElement('div');
                cellDest.className = 'item-service-dest';
                cellDest.appendChild(document.createTextNode(s.dest));

                let cellExp = document.createElement('div');
                if (s.expected[0].live) {
                    cellExp.className = 'item-service-exp ' + clLive;
                } else {
                    cellExp.className = 'item-service-exp'
                }
                cellExp.appendChild(document.createTextNode(strDue(s.expected[0].sec)));

                let cellAfter = document.createElement('div');
                cellAfter.className = 'item-service-after';

                if (s.expected.length == 2) {
                    let firstMin = document.createElement('span');
                    if (s.expected[1].live) {
                        firstMin.className = clLive;
                    }
                    firstMin.appendChild(document.createTextNode(strDue(s.expected[1].sec)))
                    cellAfter.appendChild(firstMin);
                } else if (s.expected.length > 2) {
                    let firstMin = document.createElement('span');
                    if (s.expected[1].live) {
                        firstMin.className = clLive;
                    }
                    let secondMin = document.createElement('span');
                    if (s.expected[2].live) {
                        secondMin.className = clLive;
                    }
                    firstMin.appendChild(document.createTextNode(strDue(s.expected[1].sec).replace(' min', ' and')));
                    secondMin.appendChild(document.createTextNode(strDue(s.expected[2].sec)))
                    cellAfter.appendChild(firstMin);
                    cellAfter.appendChild(document.createTextNode(' '));
                    cellAfter.appendChild(secondMin);
                }

                row.appendChild(cellNumber);
                row.appendChild(cellDest);
                row.appendChild(cellExp);
                row.appendChild(cellAfter);
                table.appendChild(row);
            }
            // Remove all existing elements
            let last = self.table.lastChild;
            while (last) {
                self.table.removeChild(last);
                last = self.table.lastChild;
            }
            // Add table
            self.table.appendChild(table);
            console.log(`Created table with ${self.data.services.length} services for stop '${self.atcoCode}'.`);

        } else {
            self.hTime.innerHTML = `No buses expected at ${self.data.local_time}`;
            console.log(`No services found for stop ${self.atcoCode}.`);
        }
    }

    /**
     * Updates seconds remaining with current date/time if no data received
     */
    function _updateData() {
        var dtNow = new Date();
        for (s of self.data.services) {
            for (e of s.expected) {
                let expDate = new Date((e.live) ? e.live_date: e.exp_date);
                e.sec = Math.round((expDate - dtNow) / 1000);
                if (e.sec < 0) {
                    let index = s.expected.indexOf(e);
                    s.expected.splice(index, 1);
                }
            }
            if (s.expected.length === 0) {
                let index = self.data.services.indexOf(s);
                self.data.services.splice(index, 1);
            }
        }
        // Sort by time remaining on first service coming
        self.data.services.sort((a, b) => a.expected[0].sec - b.expected[0].sec);
        var dtReq = new Date(self.data.iso_date);
        var overDue = Math.round((dtNow - dtReq) / 1000);
        console.log(`Simulated time remaining as live date overdue ${overDue} seconds.`);
    }

    /**
     * Starts up the class with interval for refreshing
     */
    function _initialise() {
        self.getData();
        if (REFRESH) {
            var time = INTERVAL;
            window.setInterval(function() {
                if (--time > 0) {
                    self.cd.innerHTML = `${time}s`
                } else {
                    self.cd.innerHTML = 'now';
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

var BUS = "bus-white.svg";
var TRAM = "tram-white.svg";

/**
 * Resizes text within boxes
 * @param {string} className - name of class to modify data in
 */
function resizeInd(className) {
    for (elt of document.getElementsByClassName(className)) {
        var ind = elt.innerHTML;
        if (/(Bay|Stan\.|Stand|Stop)/gi.test(ind) || ind.trim().length == 0) {
            fontSize = parseFloat(getComputedStyle(elt).fontSize);
            imgSize = Math.round(2.8 * fontSize);
            elt.innerHTML = `<img src=${BUS} width="${imgSize}px">`;
        } else {
            elt.innerHTML = ind;
            var len = ind.replace(/(&#?\w+;)/, ' ').length;
            switch(len) {
            case 1:
                elt.style.fontSize = "2.2em";
                break;
            case 2:
                elt.style.fontSize = "1.8em";
                break;
            case 3:
                elt.style.fontSize = "1.5em";
                break;
            case 4:
                elt.style.fontSize = "1.3em";
                elt.style.fontWeight = "bold";
                break;
            default:
                elt.style.fontSize = "1.1em";
                elt.style.fontWeight = "bold";
            }
        }
    }
}