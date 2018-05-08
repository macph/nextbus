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
 * Retrieves live data and displays it in a table
 * @constructor
 * @param {string} atcoCode ATCO code for stop
 * @param {string} adminAreaCode Admin area code for stop, eg 099 for South Yorkshire
 * @param {string} postURL URL to send requests to
 * @param {Element} tableElement Table element in document
 * @param {Element} timeElement Element in document showing time when data was retrieved
 * @param {Element} countdownElement Element in document showing time before next refresh
 */
function LiveData(atcoCode, adminAreaCode, postURL, tableElement, timeElement, countdownElement) {
    var self = this;
    this.atcoCode = atcoCode;
    this.adminAreaCode = adminAreaCode;
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

                let cNum = document.createElement('div');
                let cNumInner = document.createElement('div');
                cNum.className = 'row-service-line';
                cNumInner.className = 'row-service-line-inner' + ' ' + `area-color-${self.adminAreaCode}`;
                if (s.name.length > 6) {
                    cNumInner.className += ' row-service-line-small';
                }
                cNumInner.appendChild(document.createTextNode(s.name));
                cNum.appendChild(cNumInner);

                let cDest = document.createElement('div');
                cDest.className = 'row-service-dest';
                cDest.appendChild(document.createTextNode(s.dest));

                let cExp = document.createElement('div');
                cExp.className = 'row-service-exp';

                let cExpNext = document.createElement('span');
                if (s.expected[0].live) {
                    cExpNext.className = clLive;
                }
                cExpNext.appendChild(
                    document.createTextNode(strDue(s.expected[0].secs))
                );
                cExp.appendChild(cExpNext);

                let cAfter = document.createElement('div');
                cAfter.className = 'row-service-after';

                if (s.expected.length == 2) {
                    let firstMin = document.createElement('span');
                    if (s.expected[1].live) {
                        firstMin.className = clLive;
                    }
                    firstMin.appendChild(
                        document.createTextNode(strDue(s.expected[1].secs))
                    );
                    cAfter.appendChild(firstMin);
                } else if (s.expected.length > 2) {
                    let firstMin = document.createElement('span');
                    if (s.expected[1].live) {
                        firstMin.className = clLive;
                    }
                    let secondMin = document.createElement('span');
                    if (s.expected[2].live) {
                        secondMin.className = clLive;
                    }
                    firstMin.appendChild(
                        document.createTextNode(strDue(s.expected[1].secs).replace('min', 'and'))
                    );
                    secondMin.appendChild(
                        document.createTextNode(strDue(s.expected[2].secs))
                    );
                    cAfter.appendChild(firstMin);
                    cAfter.appendChild(document.createTextNode(' '));
                    cAfter.appendChild(secondMin);
                }

                table.appendChild(cNum);
                table.appendChild(cDest);
                table.appendChild(cExp);
                table.appendChild(cAfter);
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
                let expDate = new Date(e.exp_date);
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
 * @param {boolean} revert - Reverts colours of indicator
 */
function resizeInd(className, revert) {
    var elements = document.getElementsByClassName(className);
    for (let i = 0; i < elements.length; i++) {
        let elt = elements[i];
        let style = window.getComputedStyle(elt);
        let span = elt.getElementsByTagName('span');
        if (span.length !== 0) {let text = span[0];
            if (typeof revert !== 'undefined' && revert) {
                let foreground = style.getPropertyValue('color');
                let background = style.getPropertyValue('background-color');
                elt.style.backgroundColor = foreground;
                elt.style.color = background;
            }
            let ind = text.textContent;
            let len = ind.replace(/(&#?\w+;)/, ' ').length;
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
        } else {
            let img = elt.getElementsByTagName('img')[0];
            if (typeof img === 'undefined') {
                throw 'No span or image elements within stop indicator';
            }
            let fontSize = parseFloat(style.fontSize);
            img.width = Math.round(2.8 * fontSize);
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
                    s.admin_area_ref,
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
 * List of search results and a set of filtering buttons to select the right areas.
 * @constructor
 */
function SearchFilterList() {
    var self = this;
    this.divFilterAreas = document.getElementById('dFilterAreas');
    this.listElements = Array.prototype.slice.call(
        document.querySelectorAll(
            ".item-area-search, .item-place-search, .item-stop-search"
        )
    );
    this.areaNames = new Set(self.listElements.map(i => i.dataset.adminArea));
    this.selectArea = null;
    this.selectedArea = 'all';
    this.listAreas = [];
    this.groups = {};

    this.headers = {
        area: new Section('hArea', 'dAreas'),
        place: new Section('hPlace', 'dPlace'),
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
            if (!showLocal && s.className.indexOf('item-place-search') > -1) {
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
        if (self.headers.place.heading !== null) {
            if (showLocal) {
                self.headers.place.show();
            } else {
                self.headers.place.hide();
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