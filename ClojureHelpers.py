import re, sublime, sublime_plugin, sublimerepl, text_transfer
from sublimerepl import manager

# Allows running an arbitrary command in the REPL but not in the current namespace
# Example key binding:
# { "keys": ["alt+super+r"], "command": "run_command_in_repl", "args": {"command": "(user/reset)"}},
# This will run (user/reset) in the repl
class RunCommandInReplCommand(text_transfer.ReplTransferCurrent):
  def run(self, edit, command):
    external_id = self.repl_external_id()
    for rv in manager.find_repl(external_id):
      command += rv.repl.cmd_postfix
      rv.append_input_text(command)
      rv.adjust_end()
      rv.repl.write(command)
      break
    else:
      sublime.error_message("Cannot find REPL for '{}'".format(external_id))

# Allows running a function specified in arguments on the current text selected in the repl.
# Example key binding:
# { "keys": ["alt+super+d"], "command": "run_on_selection_in_repl", "args": {"function": "clojure.repl/doc"}},
# Would run (clojure.repl/doc <selected_text>) in the repl in the current namespace
class RunOnSelectionInReplCommand(text_transfer.ReplSend):
  def run(self, edit, function):
    text = "(" + function + " " + self.selected_text() +")"
    external_id = self.repl_external_id()
    super( RunOnSelectionInReplCommand, self ).run(edit, external_id, text)

  def selected_text(self):
    v = self.view
    parts = [v.substr(region) for region in v.sel()]
    return "".join(parts)

  def repl_external_id(self):
    return self.view.scope_name(0).split(" ")[0].split(".", 1)[1]

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
    f.write(self.selected_text())
    f.close()
    form = "(load-file \"" + f.name +"\")"
    external_id = self.repl_external_id()
    super( LoadSelectionInReplCommand, self ).run(edit, external_id, form)

  def selected_text(self):
    v = self.view
    parts = [v.substr(region) for region in v.sel()]
    return "".join(parts)

  def repl_external_id(self):
    return self.view.scope_name(0).split(" ")[0].split(".", 1)[1]

class RunAllClojureTestsFromProjectInReplCommand(text_transfer.ReplTransferCurrent):
  def run(self, edit):
    form = "(do (clojure.tools.namespace.repl/refresh) (apply clojure.test/run-tests (clojure.tools.namespace.find/find-namespaces-in-dir (clojure.java.io/file \"test\"))))"
    self.view.window().run_command("refresh_namespaces_in_repl")
    self.view.window().run_command("repl_send", {"external_id": self.repl_external_id(), "text": form})

class RunClojureTestsFromCurrentNamespaceInReplCommand(text_transfer.ReplTransferCurrent):
  def run(self, edit):
    if sublimerepl.manager.repl_view(self.view):
      return
    ns = re.sub("ns\s*", "", self.view.substr(self.view.find("ns\s*\S+",0)))

    default_test_ns = re.sub("(.*)(?<!-test)\\Z","\\1-test", ns, 1)
    alt_style_test_ns = re.sub("\A([^\\.]*\\.)(?!test)","\\1test.", ns, 1)
    form = "(try (clojure.test/run-tests '" + default_test_ns + ")\n  (catch Exception e\n    (clojure.test/run-tests '" + alt_style_test_ns + ")))"
    form = "(try (clojure.test/run-tests '" + ns + ")\n  (catch Exception e\n    '" + form+ "))"

    self.view.window().run_command("run_command_in_repl", {"command": "(let [r 'user/reset] (if (find-var r) ((resolve r)) (clojure.tools.namespace.repl/refresh :after r)))"})
    self.view.window().run_command("repl_send", {"external_id": self.repl_external_id(), "text": form})