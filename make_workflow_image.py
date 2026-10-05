from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
img = Image.new("RGB", (W, H), "#F7F9FC")
d = ImageDraw.Draw(img)

def font(size, bold=False):
    path = "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"
    return ImageFont.truetype(path, size)

# Header band
d.rectangle([0, 0, W, 230], fill="#0B2545")
d.rectangle([0, 230, W, 240], fill="#25D366")
d.text((W//2, 85), "AI APPOINTMENT AGENT", font=font(52, True), fill="white", anchor="mm")
d.text((W//2, 155), "Patient Workflow  —  From WhatsApp Message to Confirmed Booking", font=font(24), fill="#B8C7D9", anchor="mm")

steps = [
    ("01", "Patient Sends a Message", "The patient types a request on WhatsApp", "#25D366"),
    ("02", "WhatsApp Bridge Picks It Up", "The message is forwarded to our server in real time", "#25D366"),
    ("03", "AI Agent Understands", "The AI interprets the request using conversation context", "#3B82F6"),
    ("04", "Smart Tools Take Action", "Checks availability, books, cancels, or reschedules", "#3B82F6"),
    ("05", "Appointment Confirmed", "The appointment is saved and secured in our database", "#F59E0B"),
    ("06", "Instant Reply + Calendar Link", "Patient gets confirmation and a Google Calendar link", "#25D366"),
]

y = 300
box_h = 120
gap = 32
box_w = W - 160
x0 = 80

for i, (num, title, sub, accent) in enumerate(steps):
    # card
    d.rounded_rectangle([x0, y, x0 + box_w, y + box_h], radius=18, fill="white", outline="#E2E8F0", width=2)
    # left accent bar
    d.rounded_rectangle([x0, y, x0 + 14, y + box_h], radius=7, fill=accent)
    # step circle
    cx, cy, r = x0 + 75, y + box_h // 2, 32
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=accent)
    d.text((cx, cy), num, font=font(22, True), fill="white", anchor="mm")
    d.text((x0 + 140, y + 34), title, font=font(30, True), fill="#0B2545")
    d.text((x0 + 140, y + 74), sub, font=font(21), fill="#64748B")
    # connector
    if i < len(steps) - 1:
        ax = x0 + 75
        d.line([ax, y + box_h, ax, y + box_h + gap], fill="#CBD5E1", width=4)
        d.polygon([(ax - 9, y + box_h + gap - 10), (ax + 9, y + box_h + gap - 10), (ax, y + box_h + gap)], fill="#CBD5E1")
    y += box_h + gap

# Footer band
d.rectangle([0, H - 90, W, H], fill="#0B2545")
d.text((W//2, H - 45), "Dr. Ahmad Dental Clinic  •  Available 24/7 on WhatsApp", font=font(22, True), fill="white", anchor="mm")

out = r"C:\Users\usa\Documents\ai-agents - Copy\appointment-ai-agent\workflow_pro.png"
img.save(out)
print("saved", out)
