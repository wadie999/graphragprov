# MuSiQue few-shot candidates

- Dataset: `external/benchmarks/musique/data/musique_full_v1.0_train.jsonl`
- Random seed: `42`
- Selected: 2 cases for each of 2, 3 and 4 hops

---

## 1. 2-hop — `2hop__824500_69926`

**Question:** In WWII when did Australian troops fight in the birthplace of Erin Stewart?

**Answer:** October 1944

### Decomposition

**Hop 1**

- Question: Erin Stewart >> place of birth
- Answer: New Britain
- Supporting paragraph: `13`

**Hop 2**

- Question: when did australian troops fight in #1
- Answer: October 1944
- Supporting paragraph: `0`

### Gold supporting paragraphs

#### Paragraph 0: New Britain campaign

Initial fighting on New Britain took place around the western end of the island in December 1943 and January 1944, with US forces landing and securing bases around Arawe and Cape Gloucester. This was followed by a further landing in March 1944 around Talasea, after which little fighting took place between the ground forces on the island. In October 1944, Australian forces took over from the US troops and undertook a Landing at Jacquinot Bay the following month, before beginning a limited offensive to secure a defensive line across the island between Wide Bay and Open Bay behind which they contained the numerically greatly superior Japanese forces for the remainder of the war. The Japanese regarded the New Britain Campaign as a delaying action, and kept their forces concentrated around Rabaul in expectation of a ground assault which never came.

#### Paragraph 13: Erin Stewart

Erin Elizabeth Stewart (born May 4, 1987) is an American politician and the 40th Mayor of New Britain, Connecticut. Stewart is the daughter of former Mayor of New Britain Tim Stewart, who served from 2003 to 2011. She was elected to her first term on November 5, 2013, at the age of 26, to become the youngest mayor in New Britain's history and the city's second female mayor. Stewart was reelected to a second term on November 3, 2015, and a third term on November 7, 2017. As of 2015 she was the youngest serving female mayor in the United States for a city the size of New Britain.

---

## 2. 2-hop — `2hop__197722_3315`

**Question:** How many seasons was the performer of Rainbow a judge on American Idol?

**Answer:** one

### Decomposition

**Hop 1**

- Question: Rainbow >> performer
- Answer: Mariah Carey
- Supporting paragraph: `1`

**Hop 2**

- Question: How many seasons was #1 a judge on American Idol?
- Answer: one
- Supporting paragraph: `17`

### Gold supporting paragraphs

#### Paragraph 1: Rainbow (Mariah Carey album)

Rainbow is the seventh studio album by American singer and songwriter Mariah Carey. It was released on November 2, 1999, by Columbia Records. The album followed the same pattern as Carey's previous two albums, "Daydream" (1995) and "Butterfly" (1997), in which she began her transition into the urban market. "Rainbow" contains a mix of hip hop-influenced R&B jams, as well as a variety of slow ballads. On the album, Carey worked with David Foster and Diane Warren, who, as well as Jimmy Jam & Terry Lewis, replaced Walter Afanasieff, the main balladeer Carey worked with throughout the 90s. As a result of her separation from her husband, Tommy Mottola, Carey had more control over the musical style of this album, so she collaborated with several artists such as Jay-Z, Usher, and Snoop Dogg, as well as Missy Elliott, Joe, Da Brat, Master P, 98°, and Mystikal.

#### Paragraph 17: American Idol

Towards the end of the season, Randy Jackson, the last remaining of the original judges, announced that he would no longer serve as a judge to pursue other business ventures. Both judges Mariah Carey and Nicki Minaj also decided to leave after one season to focus on their music careers.

---

## 3. 3-hop — `3hop1__153084_701863_185766`

**Question:** Who is the cast member of NASCAR on the original broadcaster of the drama having 97 Seconds?

**Answer:** Krista Voda

### Decomposition

**Hop 1**

- Question: To which series does 97 Seconds belong?
- Answer: House
- Supporting paragraph: `6`

**Hop 2**

- Question: #1 >> original broadcaster
- Answer: Fox
- Supporting paragraph: `2`

**Hop 3**

- Question: NASCAR on #2 >> cast member
- Answer: Krista Voda
- Supporting paragraph: `14`

### Gold supporting paragraphs

#### Paragraph 2: List of House episodes

"House", also known as "House, M.D.", is an American medical drama series which premiered on Fox on November 16, 2004. "House" was created by David Shore. The show follows Dr. Gregory House (Hugh Laurie), an irascible, maverick medical genius who heads a team of diagnosticians at the fictional Princeton-Plainsboro Teaching Hospital (PPTH) in New Jersey. In a typical episode, the team is presented with an unusual case; the storyline follows the diagnosis of the patient's illness, a process often complicated by the internal competition and personal foibles of the diagnostic team. The team leader, House, frequently clashes with his boss (Dr. Lisa Cuddy (Lisa Edelstein) in seasons 1 through 7, and Dr. Eric Foreman in season 8), and his only friend, Dr. James Wilson (Robert Sean Leonard).

#### Paragraph 6: 97 Seconds

"97 Seconds" is the third episode of the fourth season of "House" and the seventy-third episode overall. It aired on October 9, 2007.

#### Paragraph 14: NASCAR Trackside

NASCAR Trackside was a NASCAR race themed show hosted by Krista Voda on Speed Channel. The show also featured former NASCAR driver Kyle Petty and SPEED personalities Rutledge Wood and Kaitlyn Vincie. Elliott Sadler and former NASCAR crew chief Jeff Hammond occasionally occupied the seat in Petty's absence. During the Michigan broadcast on August 13, 2010 Steve Byrnes announced he was leaving the show to be the host for "NASCAR Race Hub" also broadcast on Speed. In 2011, he hosted the show during the NASCAR on FOX Sprint Cup coverage.

---

## 4. 3-hop — `3hop1__117602_470455_366897`

**Question:** What country has the Embassy of Poland, in the city where the director of Rabid Dogs died?

**Answer:** Italian Republic

### Decomposition

**Hop 1**

- Question: Who had the role of director in Rabid Dogs?
- Answer: Mario Bava
- Supporting paragraph: `6`

**Hop 2**

- Question: #1 >> place of death
- Answer: Rome
- Supporting paragraph: `5`

**Hop 3**

- Question: Embassy of Poland, #2 >> country
- Answer: Italian Republic
- Supporting paragraph: `0`

### Gold supporting paragraphs

#### Paragraph 0: Embassy of Poland, Rome

The Embassy of Poland in Rome is the diplomatic mission of the Republic of Poland to the Italian Republic. The chancery is located at Via P.P.Rubens 20, Rome.

#### Paragraph 5: Mino Guerrini

Born in Rome as Giacomo Guerrini, Guerrini entered the cinema industry in 1954 as screenwriter in Marcello Pagliero's "Vergine moderna"; after several collaborations (including the screenplay of Mario Bava's "The Girl Who Knew Too Much") he made his directorial debut in an episode of the film "Amore in quattro dimensioni" and from then started a prolific career, mainly focused on comedy films. He was also a character actor, often in his own films; as actor he's probably best known for the role of Nino in Damiano Damiani's "La rimpatriata".

#### Paragraph 6: Rabid Dogs

Rabid Dogs () is an Italian film directed by Mario Bava, starring Riccardo Cucciolla, Don Backy, Lea Lander, Maurice Poli, George Eastman and Erika Dario. Taking place largely in real time, the film follows a trio of payroll robbers who kidnap a young woman and force a man with a sick child to be their getaway driver, all while trying to avoid being caught by the police.

---

## 5. 4-hop — `4hop1__32903_103178_799_909`

**Question:** When did the 5th Dalai Lama gain political control over the country which had large amounts of contact with the country the person who described evaporation is from?

**Answer:** In 1642

### Decomposition

**Hop 1**

- Question: Who was able to describe the process of evaporation?
- Answer: Wang Chong
- Supporting paragraph: `14`

**Hop 2**

- Question: What country was #1 in?
- Answer: China
- Supporting paragraph: `8`

**Hop 3**

- Question: Who had a large amount of contacts with #2 during Yuan?
- Answer: Tibet
- Supporting paragraph: `5`

**Hop 4**

- Question: When did the 5th Dalai Lama gain political control over #3 ?
- Answer: In 1642
- Supporting paragraph: `6`

### Gold supporting paragraphs

#### Paragraph 5: Sino-Tibetan relations during the Ming dynasty

The late Turrell V. Wylie, a former professor of the University of Washington, and Li Tieh-tseng argue that the reliability of the heavily censored History of Ming as a credible source on Sino-Tibetan relations is questionable, in the light of modern scholarship. Other historians also assert that these Ming titles were nominal and did not actually confer the authority that the earlier Yuan titles had. Van Praag writes that the "numerous economically motivated Tibetan missions to the Ming Court are referred to as 'tributary missions' in the Ming Shih." Van Praag writes that these "tributary missions" were simply prompted by China's need for horses from Tibet, since a viable horse market in Mongol lands was closed as a result of incessant conflict. Morris Rossabi also writes that "Tibet, which had extensive contacts with China during the Yuan, scarcely had diplomatic relations with the Ming."

#### Paragraph 6: Sino-Tibetan relations during the Ming dynasty

Rawski writes that Altan Khan's conversion to the Gelug "can be interpreted as an attempt to expand his authority in his conflict with his nominal superior, Tümen Khan." To further cement the Mongol-Tibetan alliance, the great-grandson of Altan Khan—the 4th Dalai Lama (1589–1616)—was made the fourth Dalai Lama. In 1642, the 5th Dalai Lama (1617–1682) became the first to wield effective political control over Tibet.

#### Paragraph 8: Wang Chong

Wang Chong (; 27 – c. 100 AD), courtesy name Zhongren (仲任), was a Chinese meteorologist, astronomer, and philosopher active during the Han Dynasty. He developed a rational, secular, naturalistic and mechanistic account of the world and of human beings and gave a materialistic explanation of the origin of the universe. His main work was the "Lunheng" (論衡, "Critical Essays"). This book contained many theories involving early sciences of astronomy and meteorology, and Wang Chong was even the first in Chinese history to mention the use of the square-pallet chain pump, which became common in irrigation and public works in China thereafter. Wang also accurately described the process of the water cycle.

#### Paragraph 14: Han dynasty

Han-era astronomers adopted a geocentric model of the universe, theorizing that it was shaped like a sphere surrounding the earth in the center. They assumed that the Sun, Moon, and planets were spherical and not disc-shaped. They also thought that the illumination of the Moon and planets was caused by sunlight, that lunar eclipses occurred when the Earth obstructed sunlight falling onto the Moon, and that a solar eclipse occurred when the Moon obstructed sunlight from reaching the Earth. Although others disagreed with his model, Wang Chong accurately described the water cycle of the evaporation of water into clouds.

---

## 6. 4-hop — `4hop2__72459_31688_31714_73262`

**Question:** When was the death penalty abolished in the country that recognized the government of the person most closely associated with Libya's new government, along with the country the provides the most oil in the US?

**Answer:** 1998

### Decomposition

**Hop 1**

- Question: where does most of the oil in the us come from
- Answer: the U.S.
- Supporting paragraph: `15`

**Hop 2**

- Question: Whose face was most closely associated with Libya's new government?
- Answer: Gaddafi
- Supporting paragraph: `4`

**Hop 3**

- Question: Along with the #1 , what major power recognized #2 's government at an early date?
- Answer: U.K.
- Supporting paragraph: `14`

**Hop 4**

- Question: when was the death penalty abolished in #3
- Answer: 1998
- Supporting paragraph: `8`

### Gold supporting paragraphs

#### Paragraph 4: Muammar Gaddafi

Although theoretically a collegial body operating through consensus building, Gaddafi dominated the RCC, although some of the others attempted to constrain what they saw as his excesses. Gaddafi remained the government's public face, with the identities of the other RCC members only being publicly revealed on 10 January 1970. All young men from (typically rural) working and middle-class backgrounds, none had university degrees; in this way they were distinct from the wealthy, highly educated conservatives who previously governed the country.

#### Paragraph 8: Capital punishment in the United Kingdom

Capital punishment in the United Kingdom was used from ancient times until the second half of the 20th century. The last executions in the United Kingdom were by hanging, and took place in 1964, prior to capital punishment being abolished for murder (in 1965 in Great Britain and in 1973 in Northern Ireland). Although unused, the death penalty remained a legally defined punishment for certain offences such as treason until it was completely abolished in 1998. In 2004 the 13th Protocol to the European Convention on Human Rights became binding on the United Kingdom, prohibiting the restoration of the death penalty for as long as the UK is a party to the Convention.

#### Paragraph 14: Muammar Gaddafi

After the 1969 coup, representatives of the Four Powers – France, the United Kingdom, the United States and the Soviet Union – were called to meet RCC representatives. The U.K. and U.S. quickly extended diplomatic recognition, hoping to secure the position of their military bases in Libya and fearing further instability. Hoping to ingratiate themselves with Gaddafi, in 1970 the U.S. informed him of at least one planned counter-coup. Such attempts to form a working relationship with the RCC failed; Gaddafi was determined to reassert national sovereignty and expunge what he described as foreign colonial and imperialist influences. His administration insisted that the U.S. and U.K. remove their military bases from Libya, with Gaddafi proclaiming that "the armed forces which rose to express the people's revolution [will not] tolerate living in their shacks while the bases of imperialism exist in Libyan territory." The British left in March and the Americans in June 1970.

#### Paragraph 15: United States energy independence

In total energy consumption, the U.S. was between 86% and 91% self - sufficient in 2016. In May 2011, the country became a net exporter of refined petroleum products. As of 2014, the United States was the world's third - largest producer of crude oil, after Saudi Arabia and Russia. and second largest exporter of refined products, after Russia.

