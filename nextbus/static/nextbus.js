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
 * @param {object} centre - Centre of area, with lat and long
 * @param {array} listStops - The list of stops with required attributes
 * @param {boolean} isReady - Used to set up once external script finishes loading
 * @param {function} selectCallback - Callback when clicking a marker
 */
function MultiStopMap(mapElement, centre, listStops, isReady, selectCallback) {
    var self = this;
    this.mapElement = mapElement;
    this.centre = centre;
    this.listStops = listStops;
    this.callback = selectCallback;
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
            center: {lat: self.centre.latitude, lng: self.centre.longitude},
            styles: [
                // Hide business points of interest and transit locations
                {featureType: 'poi.business', stylers: [{visibility: 'off'}]},
                {featureType: 'transit.station.bus', elementType: 'labels.icon', stylers: [{visibility: 'off'}]}
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
     * @param {string} id
     */
    this.addListener = function(marker, id) {
        google.maps.event.addListener(marker, 'click', function() {
            self.callback(id);
        });
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

    /**
     * Gets data from server, refreshing table
     * @param {function} callback - Callback to be used upon successful request
     */
    this.getData = function(callback) {
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
                    self.isLive = true;
                    self.printData();
                } else if (self.data != null) {
                    self.isLive = false;
                    self.printData();
                } else {
                    self.isLive = false;
                    self.headingTime.textContent = "No data available";
                }
                if (typeof callback !== 'undefined') {
                    callback();
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
            self.updateOutdatedData();
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
            table.className = 'list list-services';
            for (s of self.data.services) {
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
            self.headingTime.textContent = `No services expected at ${self.data.local_time}`;
            console.log(`No services found for stop ${self.atcoCode}.`);
        }
    };

    /**
     * Updates seconds remaining with current date/time if no data received
     */
    this.updateOutdatedData = function() {
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
     * @param {function} callbackInter - Function to be used when data comes in each interval.
     *     The getData() function already checks if this function is defined before calling
     * @param {function} callbackStart - Function to be used when data comes in for the first time.
     *     If this argument is undefined, the callbackInter function is used instead
     */
    this.startLoop = function(callbackInter, callbackStart) {
        var onInterval = callbackInter;
        var onStart = (typeof callbackStart !== 'undefined') ? callbackStart : callbackInter;
        if (self.loopActive) {
            if (self.loopEnding) {
                self.loopEnding = false;
            }
            if (typeof onStart !== 'undefined') {
                onStart();
            }
            return;
        } else {
            self.getData(onStart);
        }
        if (REFRESH) {
            self.loopActive = true;
            var time = INTERVAL;
            self.interval = setInterval(function () {
                time--;
                if (time > 0) {
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
                        self.getData(onInterval);
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
     * @param {function} callback - Calls function at same time
     */
    this.stopLoop = function(callback) {
        if (self.loopActive) {
            self.loopEnding = true;
        }
        if (typeof callback !== 'undefined') {
            callback();
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
 * @param {boolean} revert - Reverts colours of indicator
 */
function resizeInd(className, busImage, tramImage, revert) {
    var elements = document.getElementsByClassName(className);
    for (let i = 0; i < elements.length; i++) {
        let elt = elements[i];
        let text = elt.getElementsByTagName('span')[0];
        let style = window.getComputedStyle(elt);
        if (!text) {
          return;
        }
        if (typeof revert !== 'undefined' && revert) {
            let foreground = style.getPropertyValue('color');
            let background = style.getPropertyValue('background-color');
            elt.style.backgroundColor = foreground;
            elt.style.color = background;
        }
        var ind = text.textContent;
        if (/(Bay|Stan\.|Stand|Stop)/gi.test(ind) || ind.trim().length == 0) {
            let fontSize = parseFloat(style.fontSize);
            let imgSize = Math.round(2.8 * fontSize);
            let imgElement = document.createElement('img');
            imgElement.src = busImage
            imgElement.width = Math.round(2.8 * fontSize);
            text.remove();
            elt.appendChild(imgElement);
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
 * Handles list of stops with live data for areas and locations.
 * @constructor
 * @param {string} url - URL to get live data
 * @param {array} listStops - List of stops
 */
function ListLiveStops(url, listStops) {
    var self = this;
    this.liveStops = {}
    this.activeStop = null;

    /**
     * Initialises constructor
     */
    this.init = function() {
        for (s of listStops) {
            let index = "stop" + s.atco_code;
            let row = document.getElementById(index);
            let head = row.getElementsByClassName("item-stop-services-head")[0];
            let content = row.getElementsByClassName("item-stop-services-content")[0];
            self.liveStops[index] = {
                code: s.atco_code,
                row: row,
                head: head,
                content: content,
                data: new LiveData(
                    s.atco_code,
                    url,
                    row.getElementsByClassName("stop-live-services")[0],
                    row.getElementsByClassName("stop-live-time")[0],
                    row.getElementsByClassName("stop-live-countdown")[0]
                )
            };
            self.addSelectStop(self.liveStops[index]);
        }
    };

    /**
     * Resizes images (eg SVG bus symbol) when indicator is resized
     * @param {HTMLElement} headElement - Heading element containing the indicator
     */
    this.resizeImg = function(headElement) {
        let imgElements = headElement.getElementsByTagName('img');
        if (imgElements.length > 0) {
            let img = imgElements[0];
            let style = window.getComputedStyle(headElement);
            img.width = Math.round(2.8 * parseFloat(style.fontSize));
        }
    };

    /**
     * Collapses a section by removing its set height (assuming the CSS style has zero height)
     * @param {HTMLElement} element - Element to be collapsed 
     */
    this.collapseContent = function(element) {
        element.style.height = '';
    }

    /**
     * Expands (or shrinks) a section to its height with transition.
     * @param {HTMLElement} element - Element to be expanded 
     */
    this.resizeContent = function(element) {
        let height = element.scrollHeight;
        element.style.height = height + 20 + 'px';
    }

    /**
     * Called when a stop is selected - gets live data and close other rows
     * @param {HTMLElement} rowElement - Row element to be selected
     */
    this.selectStop = function(rowElement) {
        let r = rowElement;
        if (r.row.className === "item-stop-services") {
            r.data.startLoop(function() {
                self.resizeContent(r.content)
            });
            r.row.className = "item-stop-services-show";
            self.resizeImg(r.head);
            // Checks if another element is active; stop loop and collapse
            if (!!self.active) {
                let t = self.liveStops[self.active]
                t.data.stopLoop(function() {
                    self.collapseContent(t.content)
                });
                t.row.className = "item-stop-services";
                self.resizeImg(t.head);
            }
            self.active = 'stop' + r.code;
        } else if (r.row.className === "item-stop-services-show") {
            r.data.stopLoop(function() {
                self.collapseContent(r.content)
            });
            r.row.className = "item-stop-services";
            self.active = null;
            self.resizeImg(r.head);
        }
    };

    /**
     * Adds on click event to a row
     * @param {object} stop - Stop object in list 
     */
    this.addSelectStop = function(stop) {
        stop.head.addEventListener("click", function() {
            self.selectStop(stop);
        });
    };

    /**
     * Called when a marker is clicked - opens stop row and scrolls to it
     * @param {string} atcoCode 
     */
    this.markerSelectStop = function(atcoCode) {
        let stopElement = self.liveStops['stop' + atcoCode];
        if (stopElement.row.className === "item-stop-services") {
            self.selectStop(stopElement);
        }
        stopElement.head.scrollIntoView(true);
    }
}

/**
 * Sets up the map and buttons to be revealed when button is pressed.
 * @constructor
 * @param {MultiStopMap} mapObject 
 * @param {HTMLElement} mapElement 
 * @param {HTMLElement} buttonElement 
 * @param {function} callback 
 */
function AddMapElements(mapObject, mapElement, buttonElement, callback) {
    var self = this;
    this.map = mapObject;
    this.mapElem = mapElement;
    this.button = buttonElement;
    this.callback = callback;
    this.transitionCallback = null;

    /**
     * Checks animations to see which one is applicable, from Modernizr
     * @param {HTMLElement} element
     * @returns {string}
     */
    this.whichTransitionEvent = function(element) {
        var transitions = {
            'transition': 'transitionend',
            'OTransition': 'oTransitionEnd',
            'MozTransition': 'transitionend',
            'WebkitTransition': 'webkitTransitionEnd'
        };
        for (var t in transitions) {
            if (transitions.hasOwnProperty(t) && element.style[t] !== undefined) {
                return transitions[t];
            }
        }
    };
    this.transitionEnd = this.whichTransitionEvent(self.mapElem);

    /**
     * Initialises the map.
     */
    this.setupMap = function() {
        self.button.addEventListener('click', function() {
            this.textContent = "loading";
            self.mapElem.style.paddingBottom = "56.25%";
            this.onclick = null;
        });
        self.transitionCallback = function() {
            self.mapElem.removeEventListener(self.transitionEnd, self.transitionCallback);
            self.button.style.display = "none";
            self.map.create();
            if (typeof self.callback !== 'undefined') {
                self.callback();
            }
            console.log("Map created for stop area with " + map.markers.length + " stops.");
        }
        self.mapElem.addEventListener(self.transitionEnd, self.transitionCallback);
    }
}

/**
 * List of search results and a set of filtering buttons to select the right areas.
 * @constructor
 */
function SearchFilterList() {
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
    this.init = function() {
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