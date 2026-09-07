

async function getData() {
    const response = await fetch('https://api.fbi.gov/wanted/v1/list')
    const json = await response.json()
    console.log(json)
}

const DATA = getData()

console.log(DATA)