import Pusher from "pusher-js";
import fetch from "node-fetch";


const API_KEY = "69c3cccddb8edaab8932";
const PUSHER_KEY = "a22734a47847a64386c8"; 

console.error("🔧 DEBUG: Starting PNW listener with pusher-js...");


async function getChannel(model, event, metadata = false, since, nanos) {
  const url = new URL(`https://api.politicsandwar.com/subscriptions/v1/subscribe/${model}/${event}`);
  url.searchParams.append("api_key", API_KEY);
  url.searchParams.append("metadata", metadata ? "true" : "false");
  if (since !== undefined) url.searchParams.append("since", since.toString());
  if (nanos !== undefined) url.searchParams.append("nanos", nanos.toString());

  console.error(`🔧 DEBUG: Fetch URL: ${url.toString()}`);
  const res = await fetch(url.toString());
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }

  const data = await res.json();
  console.error(`📡 Got channel for ${model}/${event}: ${data.channel}`);
  return data.channel;
}


console.error("🔧 DEBUG: Configuring Pusher...");
const pusher = new Pusher(PUSHER_KEY, {
  cluster: "abc",
  wsHost: "socket.politicsandwar.com",
  disableStats: true,
  authEndpoint: "https://api.politicsandwar.com/subscriptions/v1/auth",
});


pusher.connection.bind("connected", () => console.error("🔗 Pusher connected"));
pusher.connection.bind("error", (err) => console.error("❌ Pusher connection error:", err));
pusher.connection.bind("disconnected", () => console.error("⚠️ Pusher disconnected"));


function subscribeToChannel(channelName) {
  console.error(`🔧 DEBUG: Subscribing to channel: ${channelName}`);
  const channel = pusher.subscribe(channelName);

  channel.bind_global((eventName, data) => {
    
    console.log(JSON.stringify({ type: eventName, channel: channelName, data }));

    
    console.error(`📨 Received event ${eventName} on ${channelName}`);
  });

  channel.bind("pusher:subscription_succeeded", () => {
    console.error(`✅ Subscribed to ${channelName}`);
  });

  channel.bind("pusher:subscription_error", (err) => {
    console.error(`❌ Subscription error on ${channelName}:`, err);
  });
}


async function start() {
  console.error("🔧 DEBUG: Starting main loop...");
  try {
    const warCreateChannel = await getChannel("war", "create", true);
    const warUpdateChannel = await getChannel("war", "update", true);

    subscribeToChannel(warCreateChannel);
    subscribeToChannel(warUpdateChannel);

    console.error("🚀 Node.js PNW listener started! Waiting for events...");
  } catch (err) {
    console.error("❌ Fatal error in start():", err);
    process.exit(1);
  }
}

start();
