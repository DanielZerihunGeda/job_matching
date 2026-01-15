From python: 3.12.3
WORKDIR /app/telegrambot

#install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

#copy in the source code
COPY bot ./bot

#Default
EXPOSE 8080

CMD ["python3" "-m" "bot"]