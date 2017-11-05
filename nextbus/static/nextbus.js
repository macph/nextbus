const INTERVAL = 60;
const REFRESH = true;

if (!Array.prototype.indexOf) {
    Array.prototype.indexOf = function(element) {
        for (var i = 0; i < this.length; i++) {
            if (this[i] === element) {
                return i;
            }
        }
        return -1;
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
        + dateObj.getMinutes() + ':'
        + dateObj.getSeconds()
    );
    return date;
}

function ServicesFilter(callback, ...args) {
    var self = this;
    this.callback = callback;
    this.services = args;
    this.filterList = [];

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

    this.reset = function() {
        if (self.filterList.length > 0) {
            console.log(`Resetting filtered list ${self.filterList}.`);
            self.filterList.length = 0;
            self.callback();
        } else {
            console.log(`Filtered list is empty.`);
        }
    }

    this.exclude = function(s) {
        return (self.filterList.length > 0 && self.filterList.indexOf(s) == -1);
    }

    this.include = function(s) {
        return (self.filterList.length > 0 && self.filterList.indexOf(s) > -1);
    }
}

function LiveData(atcoCode, postURL, tableElement, timeElement, countdownElement) {
    var self = this;
    this.atcoCode = atcoCode;
    this.postURL = postURL;
    this.table = tableElement;
    this.time = timeElement;
    this.cd = countdownElement;
    this.data = {};
    
    this.getData = _getData;
    this.printData = _printGroupData;
    this.initialise = _initialise;
    this.filter = new ServicesFilter(_printData);

    this.getAllServices = function() {
        var listServices = [];
        if (self.data.departures.all) {
            for (s of self.data.departures.all) {
                listServices.push(s.line);
            }
        }
        return [...new Set(listServices)];
    }

    function _getData() {
        console.log(`Sending POST request to ${self.postURL} with code='${self.atcoCode}'`);
        var request = new XMLHttpRequest();
        request.open('POST', self.postURL, true);
        request.setRequestHeader('Content-Type', 'application/json; charset=utf-8');
        request.onreadystatechange = function() {
            if(request.readyState === XMLHttpRequest.DONE && request.status === 200) {
                console.log(`Request for stop '${self.atcoCode}' successful`);
                self.data = JSON.parse(request.responseText)
                self.filter.services = self.getAllServices();
                self.printData(self.data)
            }
        }
        request.send(JSON.stringify({code: self.atcoCode}));
    }

    function _printGroupData() {
        var reqDate = new Date(self.data.request_time);
        var listServices = [];
        
        function _getDateTime(service, currentDate) {
            var expDate, isLive, dueMin, strDue, newService;
            var arrDate = service.expected_departure_date;
            var arrTime = service.expected_departure_time;
            if (arrDate && arrTime) {
                isLive = true;
            } else {
                isLive = false;
                arrDate = service.date;
                arrTime = service.aimed_departure_time;
            }
            expDate = new Date(arrDate + ' ' + arrTime);
            dueMin = Math.round((expDate - currentDate) / 60000);
            strDue = (dueMin < 2) ? "due" : (dueMin + " min");

            newService = {
                line: s.line,
                dest: s.direction,
                operator: s.operator,
                name: s.operator_name,
                arrivals: [{live: isLive, expected: expDate, due: strDue}]
            }

            return newService;
        }

        if (self.data.departures.all) {
            for (s of self.data.departures.all) {
                var ns = _getDateTime(s, reqDate);
                var found = false;
                for (t of listServices) {
                    if (t.line === ns.line && t.dest === ns.dest) {
                        t.arrivals.push(ns.arrivals[0]);
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    listServices.push(ns);
                }
            }
            self.time.innerHTML = `Live bus times as of ${printDate(reqDate)} - `;
            var strTable = '<div class="list-services">';
            for (s of listServices) {
                var clLive = (s.arrivals[0].live) ? " text-green" : "";
                strTable += (
                    '<a class="row-service">'
                    + `<div class="item-service-num">${s.line}</div>`
                    + `<div class="item-service-dest">${s.dest.split(' (')[0]}</div>`
                    + `<div class="item-service-exp${clLive}">${s.arrivals[0].due}</div>`
                )
                if (s.arrivals.length == 1) {
                    strTable += '<div class="item-service-after"></div>';
                } else if (s.arrivals.length == 2) {
                    var clLive1 = (s.arrivals[1].live) ? ' class="text-green"' : '';
                    strTable += `<div class="item-service-after"><span${clLive1}>${s.arrivals[1].due}</span></div>`;
                } else {
                    var first = s.arrivals[1].due;
                    var firstMin = first.substr(0, first.indexOf(' '));
                    var clLive1 = (s.arrivals[1].live) ? ' class="text-green"' : '';
                    var clLive2 = (s.arrivals[2].live) ? ' class="text-green"' : '';
                    strTable += `<div class="item-service-after"><span${clLive1}>${firstMin},</span> <span${clLive2}>${s.arrivals[2].due}</span></div>`;
                }
                strTable += '</a>';
            }
            strTable += '</div>'
            self.table.innerHTML = strTable;
            console.log(`Created table with ${self.data.departures.all.length} services for stop '${self.atcoCode}'.`)
        
        } else {
            self.time.innerHTML = `No buses expected at ${printDate(reqDate)} - `;
            self.table.innerHTML = '';
            console.log(`No services found for stop ${self.atcoCode}.`);
        }


        return listServices;
    } 

    function _printData() {
        var expDate;
        var reqDate = new Date(self.data.request_time);
        var strTable = "<p>Live bus times as of " + printDate(reqDate) + ":</p>";
        strTable += '<div class="list-services">'
        if (self.data.departures.all) {
            var count = 0;
            for (s of self.data.departures.all) {
                if (self.filter.exclude(s.line)) {
                    continue; // blacklisted by filter
                }
                if (s.expected_departure_date || s.expected_departure_time) {
                    clLive = " text-green";
                    expDate = new Date(
                        s.expected_departure_date + ' '
                        + s.expected_departure_time
                    );
                } else {
                    clLive = "";
                    expDate = new Date(s.date + ' ' + s.aimed_departure_time);
                }
                var dueMins = Math.round((expDate - reqDate) / 60000);
                var strDue = (dueMins < 2) ? "due" : (dueMins + " min");
                if (dueMins > 60)
                    break;
                strTable += (
                    '<a class="row-service">'
                    + `<div class="item-service-num">${s.line}</div>`
                    + `<div class="item-service-dest">${s.direction.split(' (')[0]}</div>`
                    + `<div class="item-service-exp${clLive}">${strDue}</div></a>`
                );
                count++;
            }
            strTable += '</div>';
            self.table.innerHTML = strTable;
            console.log(`Created table with ${count} services for stop '${self.atcoCode}'.`
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
                    self.cd.innerHTML = `refreshing in ${time} second${s}...`
                } else {
                    self.cd.innerHTML = 'refreshing now...';
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

function resizeInd(className) {
    for (elt of document.getElementsByClassName(className)) {
        var ind = elt.innerHTML;
        ind = ind.replace(/(Bay|Gate|Stance|Stand|Stop) ([A-Za-z0-9]+)/gi, "$2");
        ind = ind.replace(/adjacent/gi, "adj");
        ind = ind.replace(/after/gi, "aft");
        ind = ind.replace(/before/gi, "pre");
        ind = ind.replace(/([ENSW]+)[-\s]?bound/gi, ">$1");
        ind = ind.replace(/Eastbound/gi, ">E");
        ind = ind.replace(/Northbound/gi, ">N");
        ind = ind.replace(/Southbound/gi, ">S");
        ind = ind.replace(/Westbound/gi, ">W");
        ind = ind.replace(/-&gt;([ENSW]+)/gi, ">$1");
        ind = ind.replace(/near/gi, "nr");
        ind = ind.replace(/opposite/gi, "opp");
        ind = ind.replace(/outside/gi, "o/s");
        ind = ind.replace(/(\w{6,})/, s => s.slice(0, 4) + '.');
        ind = ind.replace(/(\w+.?) (\w+\.?) .*/, "$1 $2");
        console.log("Converting indicator '" + elt.innerHTML + "' to '" + ind + "', length " + ind.length);
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