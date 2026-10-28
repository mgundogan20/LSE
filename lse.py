import contextlib
import importlib.util
import io
import os
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
	QApplication, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
	QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QTabWidget,
	QVBoxLayout, QWidget,
)

import quine_mccluskey
from boolean_exp import boolean_exp

EXAMPLE_DIRECTORY = Path(__file__).resolve().parent / "example_eqns"
SYNTHESIS_DIRECTORY = Path(__file__).resolve().parent / "synthesis"

NODE_COLORS = {
	"AND": "#4F6BED",
	"OR": "#E07B39",
	"NOT": "#8E5BD8",
	"VARIABLE": "#2E9E6B",
	"CONSTANT": "#7A869A",
}

STYLESHEET = """
QMainWindow, QWidget#page { background: #F4F6F9; }
QFrame#header { background: #1F2937; }
QLabel#appTitle { color: #FFFFFF; font-size: 20px; font-weight: 600; }
QLabel#appSubtitle { color: #AEB6C4; font-size: 12px; }
QLabel#fileLabel { color: #E5E7EB; font-size: 13px; }
QPushButton#primary {
	background: #4F6BED; color: #FFFFFF; border: none; border-radius: 6px;
	padding: 8px 18px; font-size: 13px; font-weight: 600;
}
QPushButton#primary:hover { background: #3F59D6; }
QPushButton#primary:pressed { background: #3349B8; }
QFrame#card { background: #FFFFFF; border: 1px solid #E3E6EB; border-radius: 10px; }
QLabel#cardTitle { color: #6B7280; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
QLabel#cardValue { color: #111827; font-size: 24px; font-weight: 600; }
QLabel#cardCaption { color: #6B7280; font-size: 11px; }
QLabel#sectionTitle { color: #111827; font-size: 14px; font-weight: 600; }
QLabel#sectionCaption { color: #4F6BED; font-size: 12px; font-weight: 600; }
QLabel#sectionBody { color: #1F2937; font-size: 12px; }
QLabel#columnHeader { color: #374151; font-size: 16px; font-weight: 600; padding: 4px 2px; }
QLabel#groupHeader { color: #374151; font-size: 16px; font-weight: 600; padding: 8px 2px 2px 2px; }
QLabel#placeholder { color: #9CA3AF; font-size: 15px; }
QTabWidget::pane { border: none; background: #F4F6F9; }
QTabBar { font-size: 14px; }
QTabBar::tab {
	background: transparent; color: #6B7280; padding: 12px 24px;
	min-width: 90px; border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: #111827; border-bottom: 2px solid #4F6BED; }
QTabBar::tab:hover { color: #111827; }
QPlainTextEdit {
	background: #FFFFFF; border: 1px solid #E3E6EB; border-radius: 8px;
	padding: 8px; color: #1F2937;
}
QScrollArea { border: none; background: transparent; }
"""


def monospace_font(size=11):
	font = QFont("Consolas", size)
	font.setStyleHint(QFont.Monospace)
	return font


# ---------------------------------------------------------------- formatting

def format_literal(variable, is_complemented):
	return variable + "'" if is_complemented else variable


def format_minterm_product(index, inputs):
	bits = format(index, f"0{len(inputs)}b")
	return "·".join(format_literal(variable, bit == "0") for bit, variable in zip(bits, inputs))


def format_maxterm_sum(index, inputs):
	bits = format(index, f"0{len(inputs)}b")
	return "(" + " + ".join(format_literal(variable, bit == "1") for bit, variable in zip(bits, inputs)) + ")"


def format_cube_product(cube, inputs):
	literals = [format_literal(variable, bit == "0") for bit, variable in zip(cube, inputs) if bit != "-"]
	return "·".join(literals) if literals else "1"


def format_cube_inverted_sum(cube, inputs):
	"""An OFF-set cube is a product term of F'; by De Morgan it is a sum term of F."""
	literals = [format_literal(variable, bit == "1") for bit, variable in zip(cube, inputs) if bit != "-"]
	return "(" + " + ".join(literals) + ")" if literals else "0"


def count_cube_literals(cubes):
	return sum(len(cube) - cube.count("-") for cube in cubes)


def format_canonical_SOP(name, minterms, inputs):
	index_list = ", ".join(str(index) for index in minterms)
	expanded = " + ".join(format_minterm_product(index, inputs) for index in minterms)
	return f"{name} = Σm({index_list})\n\n{name} = {expanded}"


def format_canonical_POS(name, maxterms, inputs):
	index_list = ", ".join(str(index) for index in maxterms)
	expanded = "".join(format_maxterm_sum(index, inputs) for index in maxterms)
	return f"{name} = ΠM({index_list})\n\n{name} = {expanded}"


def expression_to_text(node):
	kind = node[0]
	if kind in ("VARIABLE", "CONSTANT"):
		return str(node[1])
	if kind == "NOT":
		child = node[1]
		if child[0] in ("VARIABLE", "CONSTANT"):
			return expression_to_text(child) + "'"
		return "(" + expression_to_text(child) + ")'"
	if kind == "AND":
		parts = []
		for child in node[1]:
			text = expression_to_text(child)
			parts.append("(" + text + ")" if child[0] == "OR" else text)
		return "·".join(parts)
	return " + ".join(expression_to_text(child) for child in node[1])


def count_tree_literals(node):
	kind = node[0]
	if kind == "VARIABLE":
		return 1
	if kind == "CONSTANT":
		return 0
	if kind == "NOT":
		return count_tree_literals(node[1])
	return sum(count_tree_literals(child) for child in node[1])


# ---------------------------------------------------------------- trees from cubes

def make_literal_node(variable, is_complemented):
	leaf = ("VARIABLE", variable)
	return ("NOT", leaf) if is_complemented else leaf


def combine_nodes(kind, children, empty_value):
	if not children:
		return ("CONSTANT", empty_value)
	if len(children) == 1:
		return children[0]
	return (kind, children)


def build_pos_tree(off_set_cubes, inputs):
	sums = []
	for cube in off_set_cubes:
		literals = [make_literal_node(variable, bit == "1") for bit, variable in zip(cube, inputs) if bit != "-"]
		sums.append(combine_nodes("OR", literals, 0))
	return combine_nodes("AND", sums, 1)


# ---------------------------------------------------------------- analysis

def instance_report(instance):
	return {
		"expression": instance.expression,
		"canonical_SOP": list(instance.get_canonical_SOP()),
		"canonical_POS": list(instance.get_canonical_POS()),
		"inverse_SOP": list(instance.get_inverse_SOP()),
		"inverse_POS": list(instance.get_inverse_POS()),
	}


def instance_from_SOP_cubes(source_instance, cubes, name):
	"""Write the cubes to an .eqn file with boolean_exp, then parse it into a new instance."""
	with tempfile.TemporaryDirectory() as directory:
		eqn_path = Path(directory) / f"{name}.eqn"
		eqn_text = source_instance.write_eqn_from_SOP_cubes(cubes, eqn_path)
		instance = boolean_exp()
		instance.parse_eqn(eqn_path)
	instance.get_onset_minterms()
	return instance, eqn_text


def analyze_eqn(path):
	"""Parse an .eqn file, minimize it, and collect the report for every version."""
	stem = Path(path).stem
	log = io.StringIO()
	with contextlib.redirect_stdout(log):
		original = boolean_exp()
		original.parse_eqn(path)
		original.get_onset_minterms()

		minterm_cubes = [f"{minterm:0{len(original.inputs)}b}" for minterm in original.get_canonical_SOP()]
		canonical, canonical_source = instance_from_SOP_cubes(original, minterm_cubes, f"{stem}_canonical")

		sop_qmc = quine_mccluskey.QMC()
		sop_cubes = list(sop_qmc.find_minimal_expression(original.get_canonical_SOP(), original.inputs))
		minimized, minimized_source = instance_from_SOP_cubes(original, sop_cubes, f"{stem}_minimized")

		# Minimized POS: minimize F' from the OFF-set, then apply De Morgan
		pos_qmc = quine_mccluskey.QMC()
		pos_cubes = list(pos_qmc.find_minimal_expression(original.get_canonical_POS(), original.inputs))

		minimized_pos = boolean_exp()
		minimized_pos.inputs = list(original.inputs)
		minimized_pos.output = original.output
		minimized_pos.expression = build_pos_tree(pos_cubes, original.inputs)
		minimized_pos.get_onset_minterms()

		original_report = instance_report(original)
		canonical_report = instance_report(canonical)
		minimized_report = instance_report(minimized)

	variable_count = len(original.inputs)
	return {
		"path": Path(path),
		"source": Path(path).read_text(),
		"canonical_source": canonical_source,
		"minimized_source": minimized_source,
		"log": log.getvalue(),
		"inputs": original.inputs,
		"output": original.output,
		"original": original_report,
		"canonical": canonical_report,
		"minimized": minimized_report,
		"sop_cubes": sop_cubes,
		"pos_cubes": pos_cubes,
		"pos_expression": minimized_pos.expression,
		"prime_implicants": list(sop_qmc.PIs),
		"essential_prime_implicants": list(sop_qmc.EPIs),
		"canonical_SOP_literals": len(original_report["canonical_SOP"]) * variable_count,
		"canonical_POS_literals": len(original_report["canonical_POS"]) * variable_count,
		"minimized_SOP_literals": count_cube_literals(sop_cubes),
		"minimized_POS_literals": count_cube_literals(pos_cubes),
		"canonical_equivalent": canonical.minterms == original.minterms,
		"sop_equivalent": minimized.minterms == original.minterms,
		"pos_equivalent": minimized_pos.minterms == original.minterms,
	}


# ---------------------------------------------------------------- synthesis

def write_blif_from_SOP_cubes(cubes, inputs, output, model_name, path):
	lines = [
		f".model {model_name}",
		".inputs " + " ".join(inputs),
		f".outputs {output}",
		".names " + " ".join(inputs) + f" {output}",
	]
	lines.extend(f"{cube} 1" for cube in cubes)
	lines.append(".end")
	blif_text = "\n".join(lines) + "\n"
	Path(path).write_text(blif_text)
	return blif_text


def run_synthesis(analysis):
	"""Write the minimized SOP as a .blif, then import synthesis.py to build the netlist and constraints.
	synthesis.py does all its work at import time, reads sys.argv[1], and uses the working directory."""
	model_name = analysis["path"].stem
	log = io.StringIO()
	previous_argv = sys.argv
	previous_directory = os.getcwd()
	with tempfile.TemporaryDirectory() as directory:
		blif_path = Path(directory) / f"{model_name}.blif"
		blif_text = write_blif_from_SOP_cubes(
			analysis["sop_cubes"], analysis["inputs"], analysis["output"], model_name, blif_path
		)
		try:
			sys.argv = ["synthesis.py", str(blif_path)]
			os.chdir(SYNTHESIS_DIRECTORY)
			specification = importlib.util.spec_from_file_location("synthesis", SYNTHESIS_DIRECTORY / "synthesis.py")
			synthesis = importlib.util.module_from_spec(specification)
			with contextlib.redirect_stdout(log):
				specification.loader.exec_module(synthesis)
		except SystemExit as error:
			raise RuntimeError(f"synthesis.py exited: {error}\n\n{log.getvalue()}") from None
		finally:
			sys.argv = previous_argv
			os.chdir(previous_directory)

	module_name = synthesis.module_name
	return {
		"module_name": module_name,
		"log": log.getvalue(),
		"blif": blif_text,
		"verilog": (SYNTHESIS_DIRECTORY / f"{module_name}.v").read_text(),
		"constraints": (SYNTHESIS_DIRECTORY / "constraints.xdc").read_text(),
		"truth_table": (SYNTHESIS_DIRECTORY / f"{module_name}_truth_table.txt").read_text(),
	}


def format_savings(canonical_literals, minimized_literals):
	saved = canonical_literals - minimized_literals
	percentage = 100 * saved / canonical_literals if canonical_literals else 0
	return f"{canonical_literals} → {minimized_literals} literals  ·  saved {saved} ({percentage:.0f}%)"


# ---------------------------------------------------------------- tree drawing

TREE_ROW_HEIGHT = 0.34    # inches per leaf row
TREE_COLUMN_WIDTH = 0.75  # inches per depth level


def layout_tree(root):
	"""Root on the left, growing right: depth is the column, each leaf gets its own row,
	and each parent sits level with the middle of its children."""
	nodes = []
	edges = []
	next_leaf_row = [0]

	def place(node, depth):
		kind = node[0]
		index = len(nodes)
		nodes.append(None)
		if kind in ("VARIABLE", "CONSTANT"):
			row = next_leaf_row[0]
			next_leaf_row[0] += 1
			label = str(node[1])
		else:
			children = [node[1]] if kind == "NOT" else node[1]
			child_indices = [place(child, depth + 1) for child in children]
			row = sum(nodes[child_index][1] for child_index in child_indices) / len(child_indices)
			edges.extend((index, child_index) for child_index in child_indices)
			label = kind
		nodes[index] = (depth, row, label, kind)
		return index

	place(root, 0)
	max_depth = max(depth for depth, _, _, _ in nodes)
	return nodes, edges, next_leaf_row[0], max_depth


def draw_tree(axes, layout, title, row_count):
	"""Draw a laid-out tree at the top of a panel that is row_count rows tall."""
	nodes, edges, leaf_count, max_depth = layout

	axes.set_facecolor("#FAFBFC")
	axes.set_xticks([])
	axes.set_yticks([])
	for spine in axes.spines.values():
		spine.set_color("#E3E6EB")
	axes.set_title(title, loc="left", fontsize=11, fontweight="bold", color="#111827", pad=10)

	# Elbow connectors: right from the parent, down/up to the child's row, right into the child
	for parent_index, child_index in edges:
		parent_depth, parent_row, _, _ = nodes[parent_index]
		child_depth, child_row, _, _ = nodes[child_index]
		elbow = parent_depth + 0.5
		axes.plot(
			[parent_depth, elbow, elbow, child_depth],
			[-(parent_row), -(parent_row), -(child_row), -(child_row)],
			color="#C3C9D3", linewidth=1.3, zorder=1,
		)

	for depth, row, label, kind in nodes:
		axes.text(
			depth, -(row), label, ha="center", va="center", color="white",
			fontsize=9, fontweight="bold", family="monospace", zorder=2,
			bbox=dict(boxstyle="round,pad=0.35", facecolor=NODE_COLORS[kind], edgecolor="none"),
		)

	axes.set_xlim(-0.6, max_depth + 0.6)
	axes.set_ylim(-(row_count - 1) - 0.8, 0.8)


# ---------------------------------------------------------------- widgets

class MetricCard(QFrame):
	def __init__(self, title, caption=""):
		super().__init__()
		self.setObjectName("card")
		layout = QVBoxLayout(self)
		layout.setContentsMargins(16, 12, 16, 12)
		layout.setSpacing(2)

		title_label = QLabel(title.upper())
		title_label.setObjectName("cardTitle")
		self.value_label = QLabel("—")
		self.value_label.setObjectName("cardValue")
		self.caption_label = QLabel(caption)
		self.caption_label.setObjectName("cardCaption")

		layout.addWidget(title_label)
		layout.addWidget(self.value_label)
		layout.addWidget(self.caption_label)

	def set_value(self, value, caption=None):
		self.value_label.setText(str(value))
		if caption is not None:
			self.caption_label.setText(caption)


class ReportSection(QFrame):
	def __init__(self, title, body, caption=""):
		super().__init__()
		self.setObjectName("card")
		layout = QVBoxLayout(self)
		layout.setContentsMargins(16, 12, 16, 14)
		layout.setSpacing(6)

		header = QHBoxLayout()
		title_label = QLabel(title)
		title_label.setObjectName("sectionTitle")
		header.addWidget(title_label)
		header.addStretch()
		if caption:
			caption_label = QLabel(caption)
			caption_label.setObjectName("sectionCaption")
			header.addWidget(caption_label)
		layout.addLayout(header)

		body_label = QLabel(body)
		body_label.setObjectName("sectionBody")
		body_label.setFont(monospace_font())
		body_label.setWordWrap(True)
		body_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
		layout.addWidget(body_label)


class TreeView(QWidget):
	"""All expression trees side by side, each growing from its root on the left."""

	def __init__(self):
		super().__init__()
		layout = QVBoxLayout(self)
		layout.setContentsMargins(24, 12, 24, 16)

		controls = QHBoxLayout()
		self.figure = Figure(facecolor="#FFFFFF", layout="constrained")
		self.canvas = FigureCanvasQTAgg(self.figure)
		self.toolbar = NavigationToolbar2QT(self.canvas, self)
		controls.addWidget(self.toolbar)
		controls.addStretch()
		legend = QLabel("   ".join(
			f"<span style='color:{color}'>■</span> {kind}" for kind, color in NODE_COLORS.items()
		))
		legend.setObjectName("cardCaption")
		controls.addWidget(legend)
		layout.addLayout(controls)

		self.scroll_area = QScrollArea()
		self.scroll_area.setWidget(self.canvas)
		self.scroll_area.setWidgetResizable(True)
		layout.addWidget(self.scroll_area, 1)

		self.figure.text(
			0.5, 0.5, "Open an .eqn file to view its expression trees",
			ha="center", va="center", fontsize=13, color="#9CA3AF",
		)

	def set_trees(self, trees):
		"""trees: {title: expression}, drawn left to right in the given order."""
		layouts = {title: layout_tree(expression) for title, expression in trees.items()}
		row_count = max(leaf_count for _, _, leaf_count, _ in layouts.values())
		column_widths = [max_depth + 1.2 for _, _, _, max_depth in layouts.values()]

		self.figure.clear()
		all_axes = self.figure.subplots(1, len(layouts), gridspec_kw={"width_ratios": column_widths})
		for axes, ((title, layout), expression) in zip(all_axes, zip(layouts.items(), trees.values())):
			draw_tree(axes, layout, f"{title}  ·  {count_tree_literals(expression)} literals", row_count)

		dpi = self.figure.dpi
		self.canvas.setMinimumSize(
			int(sum(column_widths) * TREE_COLUMN_WIDTH * dpi),
			int(max(5, row_count * TREE_ROW_HEIGHT + 0.8) * dpi),
		)
		self.canvas.draw_idle()


class MainWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("LSE — Boolean Expression Analyzer")
		self.resize(1280, 860)

		page = QWidget()
		page.setObjectName("page")
		page_layout = QVBoxLayout(page)
		page_layout.setContentsMargins(0, 0, 0, 0)
		page_layout.setSpacing(0)
		page_layout.addWidget(self.build_header())

		metrics_row = QHBoxLayout()
		metrics_row.setContentsMargins(24, 18, 24, 6)
		metrics_row.setSpacing(12)
		self.prime_implicant_card = MetricCard("Prime implicants")
		self.essential_card = MetricCard("Essential PIs")
		self.on_set_card = MetricCard("ON-set minterms", "Σm")
		self.off_set_card = MetricCard("OFF-set maxterms", "ΠM")
		self.sop_savings_card = MetricCard("SOP literals saved")
		self.pos_savings_card = MetricCard("POS literals saved")
		for card in (self.prime_implicant_card, self.essential_card, self.on_set_card,
		             self.off_set_card, self.sop_savings_card, self.pos_savings_card):
			metrics_row.addWidget(card)
		page_layout.addLayout(metrics_row)

		self.tabs = QTabWidget()
		self.tabs.setDocumentMode(True)
		self.tabs.tabBar().setElideMode(Qt.ElideNone)
		self.tabs.tabBar().setExpanding(False)
		self.report_area = QScrollArea()
		self.report_area.setWidgetResizable(True)
		self.report_area.setWidget(self.build_placeholder())
		self.tree_view = TreeView()
		self.source_view = self.build_text_view()
		self.log_view = self.build_text_view()
		self.synthesis_view = self.build_text_view()
		self.synthesis_view.setPlainText("Load an .eqn file and press Bitstream to run synthesis.py")
		self.tabs.addTab(self.tree_view, "Expression Trees")
		self.tabs.addTab(self.report_area, "Report")
		self.tabs.addTab(self.wrap_with_margins(self.source_view), "Source")
		self.tabs.addTab(self.wrap_with_margins(self.log_view), "Log")
		self.synthesis_tab = self.wrap_with_margins(self.synthesis_view)
		self.tabs.addTab(self.synthesis_tab, "Synthesis")
		self.analysis = None
		page_layout.addWidget(self.tabs, 1)

		self.setCentralWidget(page)

	def build_header(self):
		header = QFrame()
		header.setObjectName("header")
		layout = QHBoxLayout(header)
		layout.setContentsMargins(24, 16, 24, 16)

		titles = QVBoxLayout()
		titles.setSpacing(2)
		title = QLabel("Boolean Expression Analyzer")
		title.setObjectName("appTitle")
		subtitle = QLabel("Canonical forms · Quine-McCluskey minimization · Expression trees")
		subtitle.setObjectName("appSubtitle")
		titles.addWidget(title)
		titles.addWidget(subtitle)
		layout.addLayout(titles)
		layout.addStretch()

		self.file_label = QLabel("No file loaded")
		self.file_label.setObjectName("fileLabel")
		layout.addWidget(self.file_label)
		layout.addSpacing(12)

		self.equivalence_badge = QLabel()
		self.equivalence_badge.hide()
		layout.addWidget(self.equivalence_badge)
		layout.addSpacing(12)

		open_button = QPushButton("Open .eqn…")
		open_button.setObjectName("primary")
		open_button.setCursor(Qt.PointingHandCursor)
		open_button.clicked.connect(self.choose_file)
		layout.addWidget(open_button)
		layout.addSpacing(8)

		self.bitstream_button = QPushButton("Bitstream")
		self.bitstream_button.setObjectName("primary")
		self.bitstream_button.setCursor(Qt.PointingHandCursor)
		self.bitstream_button.setToolTip("Run synthesis.py on the minimized SOP: Verilog netlist, constraints.xdc and truth table")
		self.bitstream_button.setEnabled(False)
		self.bitstream_button.clicked.connect(self.generate_bitstream)
		layout.addWidget(self.bitstream_button)
		return header

	def build_placeholder(self):
		placeholder = QLabel("Open an .eqn file to generate a report")
		placeholder.setObjectName("placeholder")
		placeholder.setAlignment(Qt.AlignCenter)
		return placeholder

	def build_text_view(self):
		view = QPlainTextEdit()
		view.setReadOnly(True)
		view.setFont(monospace_font())
		return view

	def wrap_with_margins(self, widget):
		container = QWidget()
		layout = QVBoxLayout(container)
		layout.setContentsMargins(24, 16, 24, 16)
		layout.addWidget(widget)
		return container

	def choose_file(self):
		start_directory = str(EXAMPLE_DIRECTORY if EXAMPLE_DIRECTORY.exists() else Path.cwd())
		path, _ = QFileDialog.getOpenFileName(
			self, "Open equation file", start_directory, "Equation files (*.eqn);;All files (*)"
		)
		if path:
			self.load_file(path)

	def load_file(self, path):
		QApplication.setOverrideCursor(Qt.WaitCursor)
		try:
			analysis = analyze_eqn(path)
		except Exception as error:
			QApplication.restoreOverrideCursor()
			QMessageBox.critical(self, "Could not analyze file", f"{Path(path).name}\n\n{type(error).__name__}: {error}")
			return
		QApplication.restoreOverrideCursor()
		self.show_analysis(analysis)

	def generate_bitstream(self):
		QApplication.setOverrideCursor(Qt.WaitCursor)
		try:
			synthesis = run_synthesis(self.analysis)
		except Exception as error:
			QApplication.restoreOverrideCursor()
			QMessageBox.critical(self, "Synthesis failed", f"{self.analysis['path'].name}\n\n{type(error).__name__}: {error}")
			return
		QApplication.restoreOverrideCursor()
		self.synthesis_view.setPlainText(
			f"# ---- synthesis.py output\n{synthesis['log'].rstrip()}\n\n"
			f"# ---- Input BLIF (minimized SOP)\n{synthesis['blif']}\n"
			f"# ---- {SYNTHESIS_DIRECTORY / (synthesis['module_name'] + '.v')}\n{synthesis['verilog']}\n"
			f"# ---- {SYNTHESIS_DIRECTORY / 'constraints.xdc'}\n{synthesis['constraints']}\n"
			f"# ---- {SYNTHESIS_DIRECTORY / (synthesis['module_name'] + '_truth_table.txt')}\n{synthesis['truth_table']}"
		)
		self.tabs.setCurrentWidget(self.synthesis_tab)

	def show_analysis(self, analysis):
		self.analysis = analysis
		self.bitstream_button.setEnabled(True)
		inputs = analysis["inputs"]
		self.file_label.setText(f"{analysis['path'].name}   ·   {', '.join(inputs)} → {analysis['output']}")

		is_equivalent = analysis["canonical_equivalent"] and analysis["sop_equivalent"] and analysis["pos_equivalent"]
		badge_color = "#16A34A" if is_equivalent else "#DC2626"
		self.equivalence_badge.setText("✓ Equivalent" if is_equivalent else "✗ Not equivalent")
		self.equivalence_badge.setToolTip("Canonical SOP, minimized SOP and minimized POS evaluate to the same ON-set as the original")
		self.equivalence_badge.setStyleSheet(
			f"background: {badge_color}; color: white; border-radius: 10px; padding: 4px 12px; font-weight: 600;"
		)
		self.equivalence_badge.show()

		saved_SOP = analysis["canonical_SOP_literals"] - analysis["minimized_SOP_literals"]
		saved_POS = analysis["canonical_POS_literals"] - analysis["minimized_POS_literals"]
		self.prime_implicant_card.set_value(len(analysis["prime_implicants"]), "from Quine-McCluskey")
		self.essential_card.set_value(len(analysis["essential_prime_implicants"]), "must appear in every cover")
		self.on_set_card.set_value(len(analysis["original"]["canonical_SOP"]))
		self.off_set_card.set_value(len(analysis["original"]["canonical_POS"]))
		self.sop_savings_card.set_value(saved_SOP, f"{analysis['canonical_SOP_literals']} → {analysis['minimized_SOP_literals']}")
		self.pos_savings_card.set_value(saved_POS, f"{analysis['canonical_POS_literals']} → {analysis['minimized_POS_literals']}")

		self.report_area.setWidget(self.build_report(analysis))
		self.tree_view.set_trees({
			"Original": analysis["original"]["expression"],
			"Canonical SOP": analysis["canonical"]["expression"],
			"Minimized SOP": analysis["minimized"]["expression"],
		})
		self.source_view.setPlainText(
			f"# ---- Original: {analysis['path'].name}\n{analysis['source'].rstrip()}\n\n"
			f"# ---- Canonical SOP (written by write_eqn_from_SOP_cubes)\n{analysis['canonical_source']}\n"
			f"# ---- Minimized (written by write_eqn_from_SOP_cubes)\n{analysis['minimized_source']}"
		)
		self.log_view.setPlainText(analysis["log"])

	def build_report(self, analysis):
		inputs = analysis["inputs"]
		name = analysis["output"]
		inverse_name = name + "'"

		content = QWidget()
		content.setObjectName("page")
		layout = QVBoxLayout(content)
		layout.setContentsMargins(24, 12, 24, 24)
		layout.setSpacing(12)

		minimization_header = QLabel("Minimization")
		minimization_header.setObjectName("groupHeader")
		layout.addWidget(minimization_header)

		sop_terms = " + ".join(format_cube_product(cube, inputs) for cube in analysis["sop_cubes"])
		layout.addWidget(ReportSection(
			"5. Literal-minimized SOP",
			f"{name} = {sop_terms}\n\nCubes: {', '.join(analysis['sop_cubes'])}",
			format_savings(analysis["canonical_SOP_literals"], analysis["minimized_SOP_literals"]),
		))
		pos_terms = "".join(format_cube_inverted_sum(cube, inputs) for cube in analysis["pos_cubes"])
		layout.addWidget(ReportSection(
			"6. Literal-minimized POS",
			f"{name} = {pos_terms}\n\nOFF-set cubes of {inverse_name}: {', '.join(analysis['pos_cubes'])}",
			format_savings(analysis["canonical_POS_literals"], analysis["minimized_POS_literals"]),
		))

		implicant_grid = QHBoxLayout()
		implicant_grid.setSpacing(12)
		implicant_grid.addWidget(ReportSection(
			"7. Prime implicants",
			", ".join(analysis["prime_implicants"]),
			f"{len(analysis['prime_implicants'])} total",
		))
		implicant_grid.addWidget(ReportSection(
			"8. Essential prime implicants",
			", ".join(analysis["essential_prime_implicants"]) or "None — cover chosen by Petrick's method",
			f"{len(analysis['essential_prime_implicants'])} total",
		))
		layout.addLayout(implicant_grid)

		comparison_header = QLabel("Canonical forms")
		comparison_header.setObjectName("groupHeader")
		layout.addWidget(comparison_header)

		grid = QGridLayout()
		grid.setHorizontalSpacing(12)
		grid.setVerticalSpacing(12)
		versions = (("Original", "original"), ("Canonical SOP", "canonical"), ("Minimized", "minimized"))
		for column, (title, key) in enumerate(versions):
			grid.setColumnStretch(column, 1)
			report = analysis[key]
			column_header = QLabel(title)
			column_header.setObjectName("columnHeader")
			grid.addWidget(column_header, 0, column)

			sections = [
				ReportSection(
					"Expression",
					f"{name} = {expression_to_text(report['expression'])}",
					f"{count_tree_literals(report['expression'])} literals",
				),
				ReportSection("1. Canonical SOP", format_canonical_SOP(name, report["canonical_SOP"], inputs)),
				ReportSection("2. Canonical POS", format_canonical_POS(name, report["canonical_POS"], inputs)),
				ReportSection("3. Inverse canonical SOP", format_canonical_SOP(inverse_name, report["inverse_SOP"], inputs)),
				ReportSection("4. Inverse canonical POS", format_canonical_POS(inverse_name, report["inverse_POS"], inputs)),
				ReportSection(
					"9–10. ON-set / OFF-set",
					f"ON-set minterms  (Σm): {len(report['canonical_SOP'])}\n"
					f"OFF-set maxterms (ΠM): {len(report['canonical_POS'])}",
				),
			]
			for row, section in enumerate(sections, start=1):
				grid.addWidget(section, row, column)
		layout.addLayout(grid)
		layout.addStretch()
		return content


if __name__ == "__main__":
	application = QApplication(sys.argv)
	application.setStyle("Fusion")
	application.setStyleSheet(STYLESHEET)
	window = MainWindow()
	window.show()
	if len(sys.argv) > 1:
		window.load_file(sys.argv[1])
	sys.exit(application.exec_())
