import re, sublime, sublime_plugin, sublimerepl, text_transfer
from sublimerepl import manager

REFRESH_NAMESPACES_CMD = "(let [r 'user/reset] (if (find-var r) ((resolve r)) (clojure.tools.namespace.repl/refresh :after r)))"

def selected_text(s):
  v = s.view
  parts = [v.substr(region) for region in v.sel()]
  return "".join(parts)

def repl_external_id(s):
    return s.view.scope_name(0).split(" ")[0].split(".", 1)[1]

# Allows running an arbitrary command in the REPL but not in the current namespace
# Example key binding:
# { "keys": ["alt+super+r"], "command": "run_command_in_repl", "args": {"command": "(user/reset)"}},
# This will run (user/reset) in the repl
class RunCommandInReplCommand(text_transfer.ReplTransferCurrent):
  def run(self, edit, command, refresh_namespaces=False):
    if refresh_namespaces:
      self.view.window().run_command("refresh_namespaces_in_repl")

    external_id = self.repl_external_id()
    for rv in manager.find_repl(external_id):
      command += rv.repl.cmd_postfix
      rv.append_input_text(command)
      rv.adjust_end()
      rv.repl.write(command)
      break
    else:
      sublime.error_message("Cannot find REPL for '{}'".format(external_id))

# Refreshes all the namespaces in the REPL using clojure.tools.namespace
class RefreshNamespacesInReplCommand(RunCommandInReplCommand):
  def run(self, edit, clean):
    if clean:
      refresh_command = "(clojure.tools.namespace.repl/clear) " + REFRESH_NAMESPACES_CMD
    else:
      refresh_command = REFRESH_NAMESPACES_CMD
    super( RefreshNamespacesInReplCommand, self ).run(edit, refresh_command)

# Allows running an arbitrary command in the REPL in the current namespace
# Example key binding:
# { "keys": ["alt+super+r"], "command": "run_command_in_namespace_in_repl", "args": {"command": "(foo)"}},
# This will run (foo) in the repl in the current namespace.
class RunCommandInNamespaceInReplCommand(text_transfer.ReplSend):
  def run(self, edit, command, refresh_namespaces=False):

    if refresh_namespaces:
      self.view.window().run_command("refresh_namespaces_in_repl")

    external_id = repl_external_id(self)
    super( RunCommandInNamespaceInReplCommand, self ).run(edit, external_id, command)


class TestSelectedVarInReplCommand(text_transfer.ReplSend):
  def run(self, edit, refresh_namespaces=False):

    if refresh_namespaces:
      self.view.window().run_command("refresh_namespaces_in_repl")

    selected = selected_text(self)
    text = "(do (test-vars [#'" + selected +"]) (println \"tested " + selected +"\"))"
    external_id = repl_external_id(self)
    super(TestSelectedVarInReplCommand, self).run(edit, external_id, text)


# Allows running a function specified in arguments on the current text selected in the repl.
# Example key binding:
# { "keys": ["alt+super+d"], "command": "run_on_selection_in_repl", "args": {"function": "clojure.repl/doc"}},
# Would run (clojure.repl/doc <selected_text>) in the repl in the current namespace
class RunOnSelectionInReplCommand(text_transfer.ReplSend):
  def run(self, edit, function):
    text = "(" + function + " " + selected_text(self) +")"
    external_id = repl_external_id(self)
    super( RunOnSelectionInReplCommand, self ).run(edit, external_id, text)

# Opens the file containing the currently selected var in the REPL. Assumes that the var is in a file
# on the current classpath so it won't work for files that are in a Jar dependency. Assumes that
# the Sublime command line alias "subl" can be used to invoke sublime.
class OpenFileContainingVarCommand(text_transfer.ReplSend):
  def run(self, edit):
    text = """(let [{:keys [file line]} (meta #'THE_VAR)
                    file (.getPath (.getResource (clojure.lang.RT/baseLoader) file))]
                (println "Opening file" file)
                (clojure.java.shell/sh "subl" (str file ":" line))
                nil)""".replace("THE_VAR", selected_text(self))
    external_id = repl_external_id(self)
    super( OpenFileContainingVarCommand, self ).run(edit, external_id, text)

# Lists all the vars in the selected namespace or namespace alias
class ListVarsInSelectedNsCommand(text_transfer.ReplSend):
  def run(self, edit):
    text = """(let [selected-symbol 'THE_NS
                    selected-ns (get (ns-aliases *ns*) selected-symbol selected-symbol)]
                (println "\nVars in" (str selected-ns ":"))
                (println "------------------------------")
                (doseq [s (clojure.repl/dir-fn selected-ns)]
                  (println s))
                (println "------------------------------"))""".replace("THE_NS", selected_text(self))
    external_id = repl_external_id(self)
    super( ListVarsInSelectedNsCommand, self ).run(edit, external_id, text)

# Lists all the vars with their documentation in the selected namespace or namespace alias
class ListVarsWithDocsInSelectedNsCommand(text_transfer.ReplSend):
  def run(self, edit):
    text = """(let [selected-symbol 'THE_NS
                    selected-ns (get (ns-aliases *ns*) selected-symbol selected-symbol)]
                (println (str "\n" selected-ns ":"))
                (println "" (:doc (meta (the-ns selected-ns))))
                (doseq [s (clojure.repl/dir-fn selected-ns) :let [m (-> (str selected-ns "/" s) symbol find-var meta)]]
                  (println "---------------------------")
                  (println (:name m))
                  (cond
                    (:forms m) (doseq [f (:forms m)]
                                 (print "  ")
                                 (prn f))
                    (:arglists m) (prn (:arglists m)))
                  (println " " (:doc m)))
                (println "------------------------------"))""".replace("THE_NS", selected_text(self))
    external_id = repl_external_id(self)
    super( ListVarsWithDocsInSelectedNsCommand, self ).run(edit, external_id, text)

# Loads the current file in the REPL by telling the REPL to load it using the complete path
# This is much faster than the built in sublime repl command which copies the entire file into the
# REPL.
class LoadFileInReplCommand(text_transfer.ReplTransferCurrent):
  def run(self, edit):
    form = "(load-file \"" + self.view.file_name() +"\")"
    self.view.window().run_command("run_command_in_repl", {"command": form})

# Writes the selected text to a temporary file then tells the REPL to load that file.
# This is much faster than copying every character to the REPL individually which echos everything.
class LoadSelectionInReplCommand(text_transfer.ReplSend):
  def run(self, edit):
    f = open("/tmp/selection.clj", "w")
    f.write(selected_text(self))
    f.close()
    form = "(load-file \"" + f.name +"\")"
    external_id = repl_external_id(self)
    super( LoadSelectionInReplCommand, self ).run(edit, external_id, form)

