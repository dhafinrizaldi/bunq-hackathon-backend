Multimodal Bunq API + Claude MCP Payment Splitter Mobile App

User Story:

At a bar in Plein with friends, everyone has had some beers. You pay with your phone. You have the perfect app for the situation. When the payment from bunq is detected, you get a notification, do you want to split this payment? You click it. The app opens.
You see your list of friends who have the app, Jeremy, Ana, and Tim are with you at the beers so you select them and continue. Then you get asked, do you want to split equally or take a picture of the receipt. You take a picture of the receipt and confirm. Then you you get a text input field appear titled, How do you want me to split this? You either speak (speech to text) or write: 
"well Jeremy and I shared the bitterballen and he had the Leffe, I had the heineken, and Ana and tim each had a fanta". The app interprets the receipt into a list of expenses, matches these to your text inputs in proportion to the consumption per person described, and automatically sends the payment requests. A couple of days later you check your app and you see the split in your previous splits list along with the requests and their status.

Implementation:

This is a mobile app, Django is backend, React Native frontend with expo. MCP server and client for llm related tasks. Django apps so far thought of are Accounts and Splits.

Your task:

Implement the Receipt Image-> MCP -> ReceiptItems

