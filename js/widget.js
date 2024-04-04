import "./widget.css";

import { Deck, ScatterplotLayer } from 'deck.gl';

console.log('here!!!')
console.log('deck.gl', Deck);

// function render({ model, el }) {
// 	let btn = document.createElement("button");
// 	btn.classList.add("celldega-counter-button");
// 	btn.innerHTML = `count is ${model.get("value")}`;
// 	btn.addEventListener("click", () => {
// 		model.set("value", model.get("value") + 1);
// 		model.save_changes();
// 	});
// 	model.on("change:value", () => {
// 		btn.innerHTML = `count is ${model.get("value")}`;
// 	});
// 	el.appendChild(btn);
// }

export function render({ model, el }) {
	let root = document.createElement("div");
	root.style.height = "800px";
	let deck = new Deck({
	  parent: root,
	  controller: true,
	  initialViewState: { longitude: -122.45, latitude: 37.8, zoom: 15 },
	  layers: [
		new ScatterplotLayer({
		  data: [{ position: [-122.45, 37.8], color: [0, 255, 255], radius: 100}],
		  getFillColor: d => d.color,
		  getRadius: d => d.radius,
		  pickable: true,
		  onClick: d => console.log('hi hi hi', d)
		})
	  ],
	});
	el.appendChild(root);
	return () => deck.finalize();
}

export default { render };
