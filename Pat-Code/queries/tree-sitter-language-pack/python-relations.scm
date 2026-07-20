; python-relations.scm
; Captures import and inherit edges for Python source files.
; Loaded as a second pass alongside python-tags.scm by repo_intel/tag_extractor.py.
; Capture names follow the pattern:
;   name.relation.import  — the module being imported from / imported
;   name.relation.inherit — the base class name
;
; All captures that tag_extractor.py cares about must begin with "name.relation."
; so the dispatch loop can distinguish them from "name.definition.*" / "name.reference.*".


; ─────────────────────────────────────────────────────────────────────────────
; IMPORT EDGES
; ─────────────────────────────────────────────────────────────────────────────

; Case 1: `import os`  /  `import os.path`
; Captures the top-level dotted module name.
(import_statement
  name: (dotted_name) @name.relation.import)

; Case 2: `import numpy as np`
; The real module name lives inside aliased_import → dotted_name.
(import_statement
  name: (aliased_import
    name: (dotted_name) @name.relation.import))

; Case 3: `from pathlib import Path`  /  `from mypackage import MyClass, helper`
; Captures the source module (dotted_name immediately after "from").
; The module_name field is the first named child of import_from_statement.
(import_from_statement
  module_name: (dotted_name) @name.relation.import)

; Case 4: `from . import sibling`  /  `from ..utils import helper`
; Relative imports: module_name is a relative_import node.
; We capture the dotted_name inside it (if present) for the package part,
; otherwise the import_prefix alone identifies it as a relative import.
(import_from_statement
  module_name: (relative_import
    (dotted_name) @name.relation.import))


; ─────────────────────────────────────────────────────────────────────────────
; INHERIT EDGES
; ─────────────────────────────────────────────────────────────────────────────

; Case 1: `class Dog(Animal):`  — single base class
; Case 2: `class GuideDog(Dog, Animal):`  — multiple base classes
; The argument_list inside class_definition holds identifier nodes for each base.
; We capture every identifier directly inside the argument_list.
;
; Note: attribute access bases like `module.Base` are captured via the
; attribute node's last identifier (the class name itself).
(class_definition
  superclasses: (argument_list
    (identifier) @name.relation.inherit))

; Case: `class Foo(module.Base):` — dotted base class reference
; Capture the full dotted_name so the graph builder can resolve it.
(class_definition
  superclasses: (argument_list
    (attribute
      attribute: (identifier) @name.relation.inherit)))
