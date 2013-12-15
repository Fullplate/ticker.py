#!/usr/bin/python

import requests, time, smtplib, argparse

class Break:
    def __init__(self, value_type, trigger, value, actions, single=True):
        self.value_type = value_type
        self.value = value
        self.trigger = trigger
        self.actions = actions        
        self.single = single # "delete" the breakpoint after a single hit
        self.exists = True

    def check(self, curr_price, curr_spread):
        # select an argument to check based on self.value_type
        argmap = {"price":curr_price, "spread":curr_spread}
        value = argmap[self.value_type]

        if self.trigger == "under":
            return (value <= self.value and self.exists)
        elif self.trigger == "over":
            return (value >= self.value and self.exists)

    def hit(self):
        if self.single:
            self.exists = False
        return self.actions

class Ticker:
    def __init__(self, target_email, breaks):
        self.update_freq = 1 # api calls per second
        self.last = [] # stores all previous prices
        self.curr_spread_numeric = 0.0
        self.curr_spread_percent = 0.0
        self.sample_size = 10 / self.update_freq # how many seconds to sample prices over
        self.target_email = target_email
        self.breaks = breaks
        self.summary_frequency = self.update_freq * 1800 # summary updates every 1800 seconds/30 mins

        print "Retrieving data from: https://data.mtgox.com/api/2/BTCUSD/money/ticker_fast"
        print "Alerts will be sent to: " + self.target_email
        print "~"

        self.loop()

    def loop(self):
        while 1:
            self.get_data()
            self.get_spread()

            if len(self.last) >= self.sample_size:
                self.check_breaks()

            if len(self.last) % self.summary_frequency == 0:
                self.summary()

            time.sleep(self.update_freq) # update 1/sec

    def get_data(self):
        try:
            r = requests.get("https://data.mtgox.com/api/2/BTCUSD/money/ticker_fast")
        except:
            return

        root = r.json() # requests 2.x, remove () for early version

        if root["result"] != "success":
            return

        val = float(root["data"]["last"]["value"])
        val_display = root["data"]["last"]["display"]

        # display first price, and if price changes
        if len(self.last) == 0:
            print "Last price: " + val_display
        elif self.last[-1] != val: # only print val if it changes
            print "Last price: " + val_display

        self.last.append(val)

    # calculate numeric and percentage spread of prices
    def get_spread(self):
        if len(self.last) >= self.sample_size:
            spreadn = self.last[-1] - self.last[-self.sample_size] # spread between curr price and price 30 seconds ago
            spreadp = spreadn / self.last[-self.sample_size] # percentage change
            self.curr_spread_numeric = spreadn
            self.curr_spread_percent = spreadp

    # check for fulfilment of breakpoints, and perform related actions if necessary
    def check_breaks(self):
        for b in self.breaks:
            # check breakpoint to see if it's conditions are fulfilled
            if b.check(self.last[-1], self.curr_spread_percent):
                # hit the breakpoint and perform all returned actions
                for func in b.hit():
                    func(self)

    # base send email function
    def send_email(self, subject, text):
        FROM = 'TICKER'
        TO = [self.target_email]
        SUBJECT = subject
        TEXT = text

        message = """\From: %s\nTo: %s\nSubject: %s\n\n%s
        """ % (FROM, ", ".join(TO), SUBJECT, TEXT)
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.ehlo()
            server.starttls()
            server.login("YOURADDRESSHERE@gmail.com", "password")
            server.sendmail(FROM, TO, message)
            server.close()
        except:
            print "Email failed to send."

    # action functions that get triggered by a Break instance
    def alert_display(self):
        print "\n* " + str(self.sample_size) + " second spread: "\
        + str("%.2f") % self.curr_spread_numeric + " (" + str(self.curr_spread_percent) + "% change)\n"

    def alert_email(self):
        subject = "BITCOIN ALERT - $" + str(self.last[-1]) + ", " + str(self.curr_spread_numeric) + " spread!"
        text = "http://bitcoinity.org/markets"        
        self.send_email(subject, text)    

    # action functions that are called based on a certain amount of time passing
    def summary(self):
        # pretty time period display
        if self.summary_frequency < 3600:
            value = self.summary_frequency/60
            suffix = " minutes"
        elif self.summary_frequency >= 3600:
            value = self.summary_frequency/3600
            suffix = " hours"

        # calculate spreads over time period
        spreadn = self.last[-1] - self.last[-self.summary_frequency]
        spreadp = spreadn / self.last[-self.summary_frequency]

        text = "\n/-------------------------------\\\n Summary for last " + str(value) + suffix + ":\n \tNumeric spread: " + str("%.2f") % spreadn + "USD\n \tPercent spread: " + str("%.4f") % spreadp + "%\n\\-------------------------------/\n"

        print text

        # hack to get a properly substituted text string
        def return_text(txt): 
            return txt

        self.send_email("BITCOIN SUMMARY", return_text(text))

def main():
    parser = argparse.ArgumentParser(description="Bitcoin ticker and alert system.")
    parser.add_argument("email", help="Set your email address")
    args = parser.parse_args()

    breaks = [
        Break("price", "under", 900.00, [Ticker.alert_display, Ticker.alert_email]),
        Break("spread", "over", 0.0005, [Ticker.alert_display], single=True)
    ]

    Ticker(args.email, breaks)

if __name__ == "__main__":
    main()

