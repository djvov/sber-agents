const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
  method: "POST",
  headers: {
    "Authorization": "Bearer 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",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    "model": "minimax/minimax-m2:free",
    "messages": [
      {
        "role": "user",
        "content": "How are your doing?"
      }
    ]
  })
});

 if (!response.ok) {
      throw new Error(`Error! status: ${response.status}`);
    }

      const result = await  response.json();

    console.log('result is: ', JSON.stringify(result, null, 4));

  