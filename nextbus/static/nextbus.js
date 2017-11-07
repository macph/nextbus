const INTERVAL = 60;
const REFRESH = true;
const TIME_LIMIT = 60;

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
    this.hTime = timeElement;
    this.cd = countdownElement;
    this.data = {};
    
    this.getData = _getData;
    this.printData = _printData;
    this.initialise = _initialise;
    this.filter = new ServicesFilter(_printData);

    this.getAllServices = function() {
        var listServices = [];
        if (self.data.services.length > 0) {
            listServices = self.data.services.map(s => s.name);
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

    function _printData() {
        if (self.data.services.length > 0) {
            self.hTime.innerHTML = `Live times at ${self.data.local_time}`;
            var strTable = '<div class="list-services">';
            for (s of self.data.services) {
                if (self.filter.exclude(s.name)) {
                    continue;
                }
                let clLive = (s.expected[0].live) ? " text-green" : "";
                strTable += (
                    '<a class="row-service">'
                    + `<div class="item-service-num">${s.name}</div>`
                    + `<div class="item-service-dest">${s.dest}</div>`
                    + `<div class="item-service-exp${clLive}">${s.expected[0].due}</div>`
                )
                if (s.expected.length == 1) {
                    strTable += '<div class="item-service-after"></div>';
                } else if (s.expected.length == 2) {
                    let clLive1 = (s.expected[1].live) ? ' class="text-green"' : '';
                    strTable += `<div class="item-service-after"><span${clLive1}>${s.expected[1].due}</span></div>`;
                } else {
                    let first = s.expected[1].due;
                    let firstMin = first.replace(' min', '');
                    let clLive1 = (s.expected[1].live) ? ' class="text-green"' : '';
                    let clLive2 = (s.expected[2].live) ? ' class="text-green"' : '';
                    strTable += `<div class="item-service-after"><span${clLive1}>${firstMin} and</span> <span${clLive2}>${s.expected[2].due}</span></div>`;
                }
                strTable += '</a>';
            }
            strTable += '</div>';
            self.table.innerHTML = strTable;
            console.log(`Created table with ${self.data.services.length} services for stop '${self.atcoCode}'.`);
        } else {
            self.hTime.innerHTML = `No buses expected at ${printDate(reqDate)} - `;
            self.table.innerHTML = '';
            console.log(`No services found for stop ${self.atcoCode}.`);
        }
    }

    function _initialise() {
        self.getData();
        if (REFRESH) {
            var time = INTERVAL;
            window.setInterval(function() {
                if (--time > 0) {
                    let s = (time != 1) ? 's' : ''
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