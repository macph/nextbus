/*
Functions for list of stops.
*/

const INTERVAL = 60;
const REFRESH = true;
const TIME_LIMIT = 60;

/**
 * Retrieves location.
 * @param {string} elementId - element ID to output to
 */
function getLocation(elementId) {
    var output = document.getElementById(elementId);
    if (!navigator.geolocation) {
        console.log("Browser does not support geolocation.");
        output.textContent = "Geolocation not supported; try searching by postcode.";
        return;
    }
    var success = function(position) {
        var lat = position.coords.latitude.toFixed(6);
        var long = position.coords.longitude.toFixed(6);
        output.textContent = `Your position is ${lat}, ${long}. I know where you live now.`;
    }
    var error = function(err) {
        console.log("Geolocation error: " + err);
        output.textContent = "Unable to retrieve your location.";
    }
    navigator.geolocation.getCurrentPosition(success, error);
}

/**
 * Creates a Google Maps with the JS API, with marked stops.
 * @constructor
 * @param {string} mapElement - The <div> element to insert map in
 * @param {object} stopArea - Current area, with name, lat and long
 * @param {array} listStops - The list of stops with required attributes
 * @param {boolean} isReady - Used to set up once external script finishes loading
 * @param {array} listStopElements - List of live stop data with data
 * @param {function} selectStop - Function used to call stop live data
 */
function MultiStopMap(mapElement, stopArea, listStops, isReady, listStopElements, selectStop) {
    var self = this;
    this.mapElement = mapElement;
    this.stopArea = stopArea;
    this.listStops = listStops;
    this.listStopElements = listStopElements;
    this.selectStop = selectStop;
    if (isReady !== undefined && isReady) {
        this.ready = true;
    } else {
        this.ready = false;
    }

    this.setReady = function() {
        if (!self.ready) {
            self.ready = true;
        }
    }

    this.create = function() {
        if (!self.ready) {
            return;
        }
        self.map = new google.maps.Map(mapElement, {
            center: {lat: self.stopArea.latitude, lng: self.stopArea.longitude},
            styles: [
                // Hide business points of interest and transit locations
                {featureType: 'poi.business', stylers: [{visibility: 'off'}]},
                {featureType: 'transit', elementType: 'labels.icon', stylers: [{visibility: 'off'}]}
            ]
        });
        self.bounds = new google.maps.LatLngBounds();
    
        self.info = [];
        self.markers = [];
        for (stop of listStops) {
            let coord = {lat: stop.latitude, lng: stop.longitude}
            let marker = new google.maps.Marker({
                position: coord,
                map: self.map,
                title: `${stop.name} (${stop.indicator})`,
                label: {
                    fontFamily: "Source Sans Pro, sans-serif",
                    fontWeight: "600",
                    text: stop.short_ind
                }
            });
            // Add coordinates to boundary
            self.bounds.extend(coord);
            self.markers.push(marker);
            self.addListener(marker, stop.atco_code);
        }
        // Fit all coordinates within map
        self.map.fitBounds(self.bounds);
        // Zooms out to 18 if zoomed in too much
        var listener = google.maps.event.addListener(self.map, "zoom_changed", function() {
            if (self.map.getZoom() > 18) self.map.setZoom(18);
            google.maps.event.removeListener(listener); 
        });
    };

    /**
     * Adds event listener for clicking on one of the markers on the map
     * @param {google.maps.Marker} marker 
     * @param {string} atcoCode 
     */
    this.addListener = function(marker, atcoCode) {
        google.maps.event.addListener(marker, 'click', function() {
            let stopElement = self.listStopElements['stop' + atcoCode];
            if (stopElement.row.className === "item-stop-services") {
                selectStop(stopElement);
            }
            stopElement.head.scrollIntoView(true);
        });
    };
}

/**
 * Filters services in list
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
    };

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
    };

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
    };

    /**
     * Checks if whitelist is active & service is not in list, therefore excluding
     * @param {string} s - Service to check
     */
    this.exclude = function(s) {
        return (self.filterList.length > 0 && self.filterList.indexOf(s) === -1);
    };

    /**
     * Checks if whitelist is inactive or service is in list, therefore including
     * @param {string} s - Service to check
     */
    this.include = function(s) {
        return (self.filterList.length === 0 || self.filterList.indexOf(s) > -1);
    };
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
    this.headingTime = timeElement;
    this.headingCountdown = countdownElement;
    this.data = null;
    this.isLive = true;
    this.loopActive = false;
    this.loopEnding = false;
    this.filter = new ServicesFilter(this.printData);

    /**
     * Get list of all services to pass on to filtering class
     */
    this.getAllServices = function() {
        var listServices = [];
        if (self.data.services.length > 0) {
            listServices = self.data.services.map(s => s.name);
        }
        return [...new Set(listServices)];
    };

    /**
     * Gets data from server, refreshing table
     */
    this.getData = function() {
        console.log(`Sending POST request to ${self.postURL} with code='${self.atcoCode}'`);
        self.headingTime.textContent = "Updating..."
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
                    self.headingTime.textContent = "No data available";
                }
            }
        }

        request.send(JSON.stringify({code: self.atcoCode}));
    };

    /**
     * Draws table from data
     */
    this.printData = function() {
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
            self.headingTime.textContent = ((self.isLive) ? 'Live times at ' : 'Estimated times from ') + self.data.local_time;

            var table = document.createElement('div');
            table.className = 'list-services';
            for (s of self.data.services) {
                if (self.filter.exclude(s.name)) {
                    continue;
                }
                let row = document.createElement('a');
                row.className = 'row-service';

                let cellNumber = document.createElement('div');
                let cellNumberInner = document.createElement('div');
                cellNumber.className = 'row-service-line';
                cellNumberInner.className = 'row-service-line-inner' + ` area-color-${self.atcoCode.slice(0, 3)}`;
                if (s.name.length > 6) {
                    cellNumberInner.className += ' row-service-line-small';
                }
                cellNumberInner.appendChild(document.createTextNode(s.name));
                cellNumber.appendChild(cellNumberInner);

                let cellDest = document.createElement('div');
                cellDest.className = 'row-service-dest';
                cellDest.appendChild(document.createTextNode(s.dest));

                let cellExp = document.createElement('div');
                cellExp.className = 'row-service-exp';

                let cellExpNext = document.createElement('span');
                if (s.expected[0].live) {
                    cellExpNext.className = clLive;
                }
                cellExpNext.appendChild(document.createTextNode(strDue(s.expected[0].sec)));
                cellExp.appendChild(cellExpNext);

                let cellAfter = document.createElement('div');
                cellAfter.className = 'row-service-after';

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

                table.appendChild(cellNumber);
                table.appendChild(cellDest);
                table.appendChild(cellExp);
                table.appendChild(cellAfter);
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
            self.headingTime.textContent = `No buses expected at ${self.data.local_time}`;
            console.log(`No services found for stop ${self.atcoCode}.`);
        }
    };

    /**
     * Updates seconds remaining with current date/time if no data received
     */
    this.updateData = function() {
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
    };

    /**
     * Starts up the class with interval for refreshing
     */
    this.startLoop = function() {
        if (self.loopActive) {
            if (self.loopEnding) {
                self.loopEnding = false;
            }
            return;
        } else {
            self.getData();
        }
        if (REFRESH) {
            self.loopActive = true;
            var time = INTERVAL;
            self.interval = setInterval(function () {
                if (--time > 0) {
                    self.headingCountdown.textContent = `${time}s`
                } else {
                    self.headingCountdown.textContent = 'now';
                }
                if (time <= 0) {
                    if (self.loopEnding) {
                        self.loopActive = false;
                        self.loopEnding = false;
                        clearInterval(self.interval);
                    } else {
                        self.getData();
                        time = INTERVAL;
                    }
                }
            }, 1000);
        } else {
            self.headingCountdown.textContent = '';
        }
    };

    /**
     * Stops the interval, leaving it paused. Can be restarted with startLoop() again
     */
    this.stopLoop = function() {
        if (self.loopActive) {
            self.loopEnding = true;
        }
    };
}

var BUS = "bus-white.svg";
var TRAM = "tram-white.svg";

/**
 * Resizes text within boxes
 * @param {string} className - name of class to modify data in
 * @param {string} busImage - link to bus logo SVG
 * @param {string} tramImage - link to tram logo SVG
 */
function resizeInd(className, busImage, tramImage) {
    for (elt of document.getElementsByClassName(className)) {
        var text = elt.getElementsByTagName('span')[0];
        if (!text) {
          return;
        }
        var ind = text.textContent;
        if (/(Bay|Stan\.|Stand|Stop)/gi.test(ind) || ind.trim().length == 0) {
            fontSize = parseFloat(getComputedStyle(elt).fontSize);
            imgSize = Math.round(2.8 * fontSize);
            elt.innerHTML = `<img src=${busImage} width="${imgSize}px">`;
        } else {
            text.textContent = ind;
            var len = ind.replace(/(&#?\w+;)/, ' ').length;
            switch(len) {
            case 1:
                text.className = "ind-len1";
                break;
            case 2:
                text.className = "ind-len2";
                break;
            case 3:
                text.className = "ind-len3";
                break;
            case 4:
                text.className = "ind-len4";
                break;
            default:
                text.className = "";
            }
        }
    }
}

/**
 * Each section in search results has heading and list;
 * this constructor can hide them or show them.
 * @constructor
 * @param {String} headingId 
 * @param {String} listId 
 */
function Section(headingId, listId) {
    var self = this;
    this.heading = document.getElementById(headingId);
    this.list = document.getElementById(listId);

    /**
     * Hides the heading and list by adding classes
     */
    this.hide = function() {
        if (self.heading.className.indexOf('heading-hidden') === -1) {
            self.heading.className = self.heading.className + " heading-hidden";
        }
        if (self.list.className.indexOf('list-hidden') === -1) {
            self.list.className = self.list.className + " list-hidden";
        }
    };

    /**
     * Shows the heading and list by removing the hidden classes
     */
    this.show = function() {
        if (self.heading.className.indexOf('heading-hidden') > -1) {
            self.heading.className = self.heading.className.replace('heading-hidden', '');
        }
        if (self.list.className.indexOf('list-hidden') > -1) {
            self.list.className = self.list.className.replace('list-hidden', '');
        }
    };
}

/**
 * List of search results and a set of filtering buttons to select the right areas.
 * @constructor
 */
function FilterList() {
    var self = this;
    this.divFilterAreas = document.getElementById('dFilterAreas');
    this.listElements = Array.prototype.slice.call(
        document.querySelectorAll(
            ".item-area-search, .item-local-search, .item-stop-search"
        )
    );
    this.areaNames = new Set(self.listElements.map(i => i.dataset.adminArea));
    this.selectArea = null;
    this.selectedArea = 'all';
    this.listAreas = [];
    this.groups = {};

    this.headers = {
        area: new Section('hArea', 'dAreas'),
        local: new Section('hLocal', 'dLocal'),
        stop: new Section('hStop', 'dStops')
    };

    /**
     * Initialises the filter list, adding buttons if the number of areas exceed 1.
     */
    this.initialise = function() {
        if (self.areaNames.size > 1) {
            let text = document.createElement('p');
            text.textContent = "Filter by area:";
            self.divFilterAreas.appendChild(text);
            self.selectArea = document.createElement('select');
            self.divFilterAreas.appendChild(self.selectArea);

            // Add first option to show everything (default)
            let optionAll = document.createElement('option');
            optionAll.textContent = 'all';
            optionAll.value = 'all';
            self.selectArea.appendChild(optionAll);
            self.addSelectEvent(self.selectArea)

            for (a of Array.from(self.areaNames).sort()) {
                self.groups[a] = self.listElements.filter(s => s.dataset.adminArea === a);
                let option = document.createElement('option');
                option.textContent = a;
                option.value = a;
                self.selectArea.appendChild(option);
                self.listAreas.push(option)
            }
        }
    }

    /**
     * Helper function to add on 'change' event to select list
     * @param {document.Element} element 
     */
    this.addSelectEvent = function(element) {
        element.addEventListener('change', function() {
            if (self.selectedArea !== element.value) {
                if (element.value === 'all') {
                    self.showItems(self.listElements);
                } else {
                    for (g in self.groups) {
                        // Show stops and place matching specified area
                        if (self.groups.hasOwnProperty(g) && element.value === g) {
                            self.showItems(self.groups[g]);
                        // Else hide all other groups
                        } else if (self.groups.hasOwnProperty(g)) {
                            self.hideItems(self.groups[g]);
                        }
                    }
                }
                self.selectedArea = element.value;
            }
        });
    };

    /**
     * Show all item elements in list; will hide sections if all items within are excluded
     * @param {Array} list 
     */
    this.showItems = function(list) {
        let showAreas = false, showLocal = false, showStops = false;
        for (s of list) {
            if (s.className.indexOf('item-hidden') > -1) {
                s.className = s.className.replace('item-hidden', '');
            }
            if (!showAreas && s.className.indexOf('item-area-search') > -1) {
                showAreas = true;
            }
            if (!showLocal && s.className.indexOf('item-local-search') > -1) {
                showLocal = true;
            }
            if (!showStops && s.className.indexOf('item-stop-search') > -1) {
                showStops = true;
            }
        }
        console.log("area, local, place:" + showAreas + ' ' + showLocal + ' ' + showStops)
        if (self.headers.area.heading !== null) {
            if (showAreas) {
                self.headers.area.show();
            } else {
                self.headers.area.hide();
            }
        }
        if (self.headers.local.heading !== null) {
            if (showLocal) {
                self.headers.local.show();
            } else {
                self.headers.local.hide();
            }
        }
        if (self.headers.stop.heading !== null) {
            if (showStops) {
                self.headers.stop.show();
            } else {
                self.headers.stop.hide();
            }
        }
    }

    /**
     * Hide all item elements in list
     * @param {Array} list 
     */
    this.hideItems = function(list) {
        for (s of list) {
            if (s.className.indexOf('item-hidden') === -1) {
                s.className = s.className + " item-hidden";
            }
        }
    }
}