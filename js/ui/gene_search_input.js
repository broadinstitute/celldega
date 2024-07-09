// Create an input field with a datalist for autocomplete
export let input 

export const set_input =  () => {
    input = document.createElement("input");
    input.setAttribute('type', 'text');
    input.setAttribute('placeholder', 'Search gene');
    input.style.width = "500px";
    input.style.height = "20px"; 
    input.style.marginTop = "5px";
    input.style.display = "inline-block";
    input.style.padding = "1pt 2pt";
}