{:user {:dependencies []
        :injections [(use '[clojure.pprint :only [pp pprint]])
                     (use 'alex-and-georges.debug-repl)]
        :plugins [[lein-ancient "0.5.2"]]}}